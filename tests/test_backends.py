import json
import sys
import threading
import types
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

np = pytest.importorskip("numpy")

from modeldiffr.backends import detect_backend, make_backend  # noqa: E402
from modeldiffr.backends.api import APIBackend, APIError  # noqa: E402


def test_detect_backend():
    assert detect_backend("org/model") == "hf"
    assert detect_backend("./m.Q4_K_M.gguf") == "llamacpp"
    assert detect_backend("org/model", "vllm") == "vllm"
    with pytest.raises(ValueError):
        make_backend("nope", "m")
    with pytest.raises(ValueError, match="api-base"):
        make_backend("api", "m")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.requests.append((self.path, body, self.headers.get("Authorization")))
        if self.path.endswith("/completions") and "chat" not in self.path:
            if self.server.no_logprobs:
                out = {"choices": [{"text": "x"}]}
            else:
                text = body["prompt"]
                words = text.split(" ")
                tokens, offsets, pos = [], [], 0
                for i, w in enumerate(words):
                    tok = w if i == 0 else " " + w
                    tokens.append(tok)
                    offsets.append(pos)
                    pos += len(tok)
                tokens.append("<gen>")
                offsets.append(pos)
                values = [None] + [-1.0] * (len(tokens) - 1)
                out = {
                    "choices": [
                        {
                            "text": text,
                            "logprobs": {
                                "tokens": tokens,
                                "token_logprobs": values,
                                "text_offset": offsets,
                            },
                        }
                    ]
                }
        else:
            out = {"choices": [{"message": {"content": "Sure, here you go."}}]}
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    srv.requests = []
    srv.no_logprobs = False
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield srv
    srv.shutdown()


def test_api_backend(server):
    b = APIBackend(
        "my-model", f"http://127.0.0.1:{server.server_port}/v1", api_key="secret-key-123"
    )
    assert b.choice_logprob("The cat sat", " on the mat") == -3.0
    assert b.generate("hi", 8) == "Sure, here you go."
    path, body, auth = server.requests[-1]
    assert (
        path == "/v1/chat/completions"
        and body["temperature"] == 0
        and auth == "Bearer secret-key-123"
    )
    assert b.metadata()["base_url"].endswith("/v1") and "secret-key-123" not in json.dumps(
        b.metadata()
    )
    server.no_logprobs = True
    with pytest.raises(APIError, match="log probabilities"):
        b.choice_logprob("a", " b")


def _gguf(path, tokens):
    gguf = pytest.importorskip("gguf")
    w = gguf.GGUFWriter(str(path), "llama")
    w.add_context_length(256)
    w.add_tokenizer_model("gpt2")
    w.add_token_list(tokens)
    w.add_bos_token_id(0)
    w.add_eos_token_id(1)
    w.add_chat_template(
        "{% for m in messages %}<|user|> {{ m['content'] }}{% endfor %}<|assistant|>"
    )
    w.add_tensor("token_embd.weight", np.arange(64, dtype=np.float32).reshape(8, 8))
    w.add_tensor("blk.0.attn_q.weight", np.ones((8, 8), dtype=np.float16))
    q8 = np.zeros(34 * 2, dtype=np.uint8)
    w.add_tensor(
        "blk.0.ffn_down.weight", q8, raw_shape=(1, 68), raw_dtype=gguf.GGMLQuantizationType.Q8_0
    )
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file()
    w.close()
    return path


def test_gguf_fingerprint(tmp_path):
    from modeldiffr.fingerprint import diff_weights, weights_fingerprint
    from modeldiffr.fingerprint.gguf import gguf_vocab, read_gguf

    tokens = ["<s>", "</s>", "hello", "world"]
    a = _gguf(tmp_path / "a.gguf", tokens)
    info = read_gguf(a)
    assert {t["name"] for t in info["tensors"]} == {
        "token_embd.weight",
        "blk.0.attn_q.weight",
        "blk.0.ffn_down.weight",
    }
    fp = weights_fingerprint(a)
    assert fp.format == "gguf" and fp.tensors == 3 and fp.bytes == 64 * 4 + 64 * 2 + 68
    assert gguf_vocab(a)["tokens"] == tokens
    (tmp_path / "b").mkdir()
    b = _gguf(tmp_path / "b" / "m.gguf", tokens)
    assert weights_fingerprint(tmp_path / "b").root == fp.root
    data = bytearray(b.read_bytes())
    data[-1] ^= 0xFF
    b.write_bytes(bytes(data))
    assert weights_fingerprint(b).root == fp.root
    meta = read_gguf(b)
    t = next(x for x in meta["tensors"] if x["name"] == "blk.0.ffn_down.weight")
    data[meta["data_start"] + t["offset"] + 3] ^= 0xFF
    b.write_bytes(bytes(data))
    d = diff_weights(fp.leaves, weights_fingerprint(b).leaves)
    assert d["changed"] == ["blk.0.ffn_down.weight"]


class _FakeLlama:
    def __init__(self, model_path, n_ctx, n_gpu_layers, logits_all, seed, verbose):
        self.vocab = {"<s>": 0, "</s>": 1, "hello": 2, "world": 3}
        self.scores = []
        self.n_gpu_layers = n_gpu_layers

    def tokenize(self, data, add_bos=True, special=True):
        ids = [self.vocab.get(w, 2) for w in data.decode().split()]
        return ([0] if add_bos else []) + ids

    def reset(self):
        self.scores = []

    def eval(self, ids):
        self.scores = [[float((i + j) % 4) for j in range(4)] for i in range(len(ids))]

    def create_completion(self, text, max_tokens, temperature, top_k, seed):
        return {"choices": [{"text": " world"}]}


def test_llamacpp_backend(tmp_path, monkeypatch):
    path = _gguf(tmp_path / "m.gguf", ["<s>", "</s>", "hello", "world"])
    monkeypatch.setitem(sys.modules, "llama_cpp", types.SimpleNamespace(Llama=_FakeLlama))
    b = make_backend("llamacpp", str(path), n_ctx=256)
    assert b.max_context() == 256
    assert b.render_chat("hi") == "<|user|> hi<|assistant|>"
    assert b.generate("hi", 4) == " world"
    lp = b.choice_logprob("hello", " world")
    assert lp < 0
    fp = b.fingerprint()
    assert fp["weights"]["format"] == "gguf" and fp["tokenizer"]["chat_template"].startswith(
        "sha256:"
    )
    other = make_backend("llamacpp", str(path), n_ctx=256)
    assert b.divergence_to(other, "hello world") == 0.0


def test_vllm_backend_with_fake_engine(tmp_path, monkeypatch):
    transformers = pytest.importorskip("transformers")
    pytest.importorskip("torch")
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from test_hf_integration import _save

    model_dir = _save(tmp_path / "m", 0)
    tok = transformers.AutoTokenizer.from_pretrained(str(model_dir))

    class Logprob:
        def __init__(self, v):
            self.logprob = v

    class Params:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    class LLM:
        def __init__(self, **kw):
            self.kw = kw

        def get_tokenizer(self):
            return tok

        def generate(self, prompts, params, use_tqdm=False):
            outs = []
            for p in prompts:
                if getattr(params, "prompt_logprobs", None):
                    ids = p["prompt_token_ids"]
                    lps = [None] + [{t: Logprob(-0.25)} for t in ids[1:]]
                    outs.append(types.SimpleNamespace(prompt_logprobs=lps, outputs=[]))
                else:
                    outs.append(types.SimpleNamespace(outputs=[types.SimpleNamespace(text="ok")]))
            return outs

    monkeypatch.setitem(sys.modules, "vllm", types.SimpleNamespace(LLM=LLM, SamplingParams=Params))
    b = make_backend("vllm", str(model_dir))
    n = len(tok("Question: What is 7 multiplied by 8?\nAnswer: 56")["input_ids"]) - len(
        tok("Question: What is 7 multiplied by 8?\nAnswer:")["input_ids"]
    )
    assert b.choice_logprob(
        "Question: What is 7 multiplied by 8?\nAnswer:", " 56"
    ) == pytest.approx(-0.25 * n)
    assert b.generate_raw_batch(["a", "b"], 4) == ["ok", "ok"]
    assert b.fingerprint()["weights"]["format"] == "safetensors"
    assert b.supports_divergence is False
