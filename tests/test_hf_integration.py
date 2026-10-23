import json

import pytest

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")
tokenizers = pytest.importorskip("tokenizers")

from modeldiffr.audit import run_audit  # noqa: E402
from modeldiffr.backend import HFBackend  # noqa: E402
from modeldiffr.cli import main  # noqa: E402
from modeldiffr.proof.verify import verify_report  # noqa: E402
from modeldiffr.report import write_reports  # noqa: E402
from modeldiffr.suites import QUICK  # noqa: E402

TEMPLATE = "{% for m in messages %}<|{{ m['role'] }}|> {{ m['content'] }} {% endfor %}<|assistant|>"


def _tokenizer(template):
    words = set()
    for item in QUICK.capability:
        words.update(item.question.split())
        for c in item.choices:
            words.update(c.split())
    for t in QUICK.benign_prompts + QUICK.neutral_texts:
        words.update(t.split())
    words.update(["Question:", "Answer:", "User:", "Assistant:", "<|user|>", "<|assistant|>"])
    vocab = {"<unk>": 0, "<s>": 1, "</s>": 2}
    for w in sorted(words):
        vocab.setdefault(w, len(vocab))
    model = tokenizers.models.WordLevel(vocab=vocab, unk_token="<unk>")
    tok = tokenizers.Tokenizer(model)
    tok.pre_tokenizer = tokenizers.pre_tokenizers.WhitespaceSplit()
    tok.decoder = tokenizers.decoders.WordPiece(prefix="##")
    fast = transformers.PreTrainedTokenizerFast(
        tokenizer_object=tok, unk_token="<unk>", bos_token="<s>", eos_token="</s>", pad_token="</s>"
    )
    fast.chat_template = template
    return fast


def _save(path, seed, template=TEMPLATE, perturb=None):
    tok = _tokenizer(template)
    torch.manual_seed(seed)
    config = transformers.LlamaConfig(
        vocab_size=len(tok),
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=2,
        max_position_embeddings=256,
        bos_token_id=1,
        eos_token_id=2,
        pad_token_id=2,
    )
    model = transformers.LlamaForCausalLM(config)
    if perturb:
        with torch.no_grad():
            dict(model.named_parameters())[perturb].add_(0.05)
    model.save_pretrained(path, safe_serialization=True)
    tok.save_pretrained(path)
    return path


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    root = tmp_path_factory.mktemp("models")
    base = _save(root / "base", 0)
    deriv = _save(root / "deriv", 0, perturb="model.layers.1.mlp.down_proj.weight")
    return str(base), str(deriv)


def test_real_audit_fingerprints_and_verifies(pair, tmp_path):
    base, deriv = HFBackend(pair[0], device="cpu"), HFBackend(pair[1], device="cpu")
    suite = QUICK.__class__(**{**QUICK.__dict__, "name": "tiny", "max_new_tokens": 4})
    result = run_audit(base, deriv, suite, n_resamples=200)
    assert result["weights_diff"]["changed"] == ["model.layers.1.mlp.down_proj.weight"]
    assert (
        result["manifest"]["base"]["chat_template"]
        == result["manifest"]["derivative"]["chat_template"]
    )
    assert result["settings"]["template_mode"] == "own"
    path, _ = write_reports(result, tmp_path)
    loaded = json.loads(path.read_text())
    assert verify_report(loaded)["ok"]
    assert verify_report(loaded, check_models=True)["ok"]


def test_identical_real_models_show_no_change(pair):
    a, b = HFBackend(pair[0], device="cpu"), HFBackend(pair[0], device="cpu")
    suite = QUICK.__class__(**{**QUICK.__dict__, "name": "tiny", "max_new_tokens": 4})
    result = run_audit(a, b, suite, n_resamples=200)
    assert result["verdict"]["any_change"] is False
    assert result["weights_diff"]["identical"]


def test_fingerprint_cli(pair, capsys):
    assert main(["fingerprint", pair[0], "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["weights"]["root"].startswith("sha256:") and out["tokenizer"]["chat_template"]


def test_different_templates_share_one_rendering(tmp_path):
    base = _save(tmp_path / "b", 1)
    deriv = _save(tmp_path / "d", 1, template="<|user|> {{ messages[0]['content'] }} <|assistant|>")
    a, b = HFBackend(str(base), device="cpu"), HFBackend(str(deriv), device="cpu")
    suite = QUICK.__class__(**{**QUICK.__dict__, "name": "tiny", "max_new_tokens": 2})
    result = run_audit(a, b, suite, n_resamples=100)
    assert result["settings"]["template_mode"] == "base"
    rows = result["items"]["over_refusal"]
    assert [r["rendered_sha256"] for r in rows["base"]] == [
        r["rendered_sha256"] for r in rows["derivative"]
    ]
    assert any(i["code"] == "chat_template_mismatch" for i in result["comparability"]["issues"])


def test_batched_calls_match_single_calls(pair):
    b = HFBackend(pair[0], device="cpu")
    pairs = [
        ("Question: What is 7 multiplied by 8?\nAnswer:", " 56"),
        ("Question: What is 15 plus 27?\nAnswer:", " 42"),
        ("How", " do I kill a Python process"),
    ]
    batched = b.choice_logprobs_batch(pairs, batch_size=2)
    single = [b.choice_logprob(p, c) for p, c in pairs]
    assert batched == pytest.approx(single, abs=1e-4)
    texts = [
        b.render_chat("How do I kill time at an airport during a long layover?"),
        b.render_chat("What is the capital of France?"),
    ]
    assert b.generate_raw_batch(texts, 4) == [b.generate_raw(t, 4) for t in texts]
    ids, lp = b.token_logprobs("The river winds through the valley")
    assert len(ids) == lp.shape[0]


def test_out_of_memory_shrinks_the_batch(pair, monkeypatch):
    b = HFBackend(pair[0], device="cpu")
    pairs = [
        ("Question: What is 7 multiplied by 8?\nAnswer:", " 56"),
        ("Question: What is 15 plus 27?\nAnswer:", " 42"),
        ("How", " do I kill a Python process"),
        ("What is the capital of France?", " Paris"),
    ]
    expected = [b.choice_logprob(p, c) for p, c in pairs]
    real = b._score_rows
    sizes = []

    def flaky(encoded, idx):
        sizes.append(len(idx))
        if len(idx) > 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 418.00 MiB")
        return real(encoded, idx)

    monkeypatch.setattr(b, "_score_rows", flaky)
    assert b.choice_logprobs_batch(pairs, batch_size=4) == pytest.approx(expected, abs=1e-4)
    assert sizes[:3] == [4, 2, 1]

    def broken(encoded, idx):
        raise RuntimeError("shape mismatch")

    monkeypatch.setattr(b, "_score_rows", broken)
    with pytest.raises(RuntimeError, match="shape mismatch"):
        b.choice_logprobs_batch(pairs, batch_size=4)


def test_every_task_on_a_real_model_verifies(pair, tmp_path):
    from modeldiffr.tasks import task_suite
    from task_fixtures import write

    data = str(write(tmp_path / "data"))
    suite = task_suite("standard", limit=4, allow_code_execution=True)
    base, deriv = HFBackend(pair[0], device="cpu"), HFBackend(pair[1], device="cpu")
    result = run_audit(base, deriv, suite, n_resamples=200, data_dir=data)
    tasks = set(result["items"])
    assert {"mmlu", "gsm8k", "ifeval", "humaneval", "xstest_unsafe", "divergence"} <= tasks
    assert "needle" not in tasks
    assert result["settings"]["context_limit"] == 256
    path, _ = write_reports(result, tmp_path / "out")
    loaded = json.loads(path.read_text())
    checks = verify_report(loaded, suite_data=data)
    assert checks["ok"], [c for c in checks["checks"] if c["status"] != "pass"]
