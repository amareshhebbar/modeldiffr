import pytest

from modeldiffr.checks import check_pair, resolve_template_mode
from modeldiffr.fingerprint import tokenizer_fingerprint


class Tok:
    def __init__(self, vocab, template=None, eos="</s>"):
        self._vocab = vocab
        self.chat_template = template
        self.bos_token = None
        self.eos_token = eos
        self.pad_token = None
        self.unk_token = None
        self.additional_special_tokens = []

    def get_vocab(self):
        return dict(self._vocab)


def fp(tok):
    return {"tokenizer": tokenizer_fingerprint(tok), "weights": None, "commit": None}


def test_tokenizer_fingerprint_is_order_independent():
    a = tokenizer_fingerprint(Tok({"a": 0, "b": 1}, "T"))
    b = tokenizer_fingerprint(Tok({"b": 1, "a": 0}, "T"))
    assert a == b and a["vocab_size"] == 2
    c = tokenizer_fingerprint(Tok({"a": 0, "b": 1}, "T2"))
    assert c["vocab"] == a["vocab"] and c["chat_template"] != a["chat_template"]
    assert tokenizer_fingerprint(Tok({"a": 0}))["chat_template"] is None


def test_tokenizer_json_is_hashed_canonically(tmp_path):
    (tmp_path / "tokenizer.json").write_text('{"b": 1, "a": [1, 2]}')
    a = tokenizer_fingerprint(Tok({"a": 0}), tmp_path)["tokenizer_json"]
    (tmp_path / "tokenizer.json").write_text('{ "a" : [1,2],\n "b":1 }')
    assert tokenizer_fingerprint(Tok({"a": 0}), tmp_path)["tokenizer_json"] == a


def test_template_mode_resolution():
    same = fp(Tok({"a": 0}, "T"))
    other_tpl = fp(Tok({"a": 0}, "U"))
    other_vocab = fp(Tok({"z": 0}, "U"))
    no_tpl = fp(Tok({"a": 0}))
    assert resolve_template_mode("auto", same, same) == "own"
    assert resolve_template_mode("auto", same, other_tpl) == "base"
    assert resolve_template_mode("auto", no_tpl, other_tpl) == "derivative"
    assert resolve_template_mode("auto", same, other_vocab) == "own"
    assert resolve_template_mode("auto", None, same) == "own"
    assert resolve_template_mode("derivative", same, other_tpl) == "derivative"
    with pytest.raises(ValueError):
        resolve_template_mode("nope", same, same)


def test_issues():
    a, b = fp(Tok({"a": 0}, "T")), fp(Tok({"a": 0}, "U", eos="<eos>"))
    r = check_pair(a, b, {"dtype": "f32"}, {"dtype": "bf16"}, "base")
    codes = {i["code"]: i["level"] for i in r["issues"]}
    assert r["ok"]
    assert codes == {
        "chat_template_mismatch": "warning",
        "special_tokens_mismatch": "warning",
        "dtype_mismatch": "warning",
    }
    c = fp(Tok({"z": 0}, "U"))
    bad = check_pair(a, c, {}, {}, "base")
    assert not bad["ok"]
    assert {i["code"] for i in bad["issues"]} >= {
        "shared_template_needs_same_vocab",
        "vocab_mismatch",
    }
    none = check_pair(None, None, {}, {}, "own")
    assert none["ok"] and none["issues"][0]["code"] == "missing_fingerprint"
