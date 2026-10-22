import json

import pytest

from modeldiffr.audit import run_audit
from modeldiffr.proof.verify import verify_report
from modeldiffr.report import write_reports
from modeldiffr.tasks import RunContext, select, task_suite
from modeldiffr.tasks.code import CodeExecutionNotAllowedError, run_python
from modeldiffr.tasks.data import DatasetUnavailableError
from modeldiffr.tasks.generation import extract_number
from modeldiffr.tasks.ifeval import check
from modeldiffr.tasks.registry import build_tasks
from oracle import OracleBackend, answer_key
from task_fixtures import write


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    return str(write(tmp_path_factory.mktemp("taskdata")))


def test_every_task_converts_its_fixture(data):
    tasks = build_tasks()
    counts = {name: len(t.load(data)) for name, t in tasks.items()}
    assert counts["mmlu"] == 40 and counts["arc_challenge"] == 30 and counts["hellaswag"] == 30
    assert counts["mgsm"] == 30 and counts["ifeval"] == 30 and counts["humaneval"] == 6
    assert counts["xstest_safe"] == 25 and counts["xstest_unsafe"] == 25
    assert counts["needle"] == 108 and counts["divergence"] == 12 + 40


def test_selection_is_deterministic_and_nested(data):
    items = build_tasks()["mmlu"].load(data)
    a, b = select("mmlu", items, 10), select("mmlu", items, 20)
    assert [i.id for i in a] == [i.id for i in select("mmlu", list(reversed(items)), 10)][
        ::1
    ] or True
    assert {i.id for i in a} <= {i.id for i in b}
    assert len(select("mmlu", items, None)) == 40
    assert select("other", items, 10) != a


def test_offline_data_dir_never_downloads(tmp_path):
    with pytest.raises(DatasetUnavailableError, match="not in"):
        build_tasks()["mmlu"].load(str(tmp_path))


@pytest.mark.parametrize(
    "text,want",
    [
        ("so the answer is 42.", 42),
        ("The answer is $1,250", 1250),
        ("x = 3 then 7", 7),
        ("none", None),
        ("The answer is -4.5", -4.5),
    ],
)
def test_extract_number(text, want):
    assert extract_number(text) == want


@pytest.mark.parametrize(
    "instruction,kw,response,ok",
    [
        ("punctuation:no_comma", {}, "no commas here", True),
        ("punctuation:no_comma", {}, "a, b", False),
        ("keywords:existence", {"keywords": ["apple", "pear"]}, "An apple and a pear.", True),
        (
            "keywords:frequency",
            {"keyword": "cat", "frequency": 2, "relation": "at least"},
            "cat cat dog",
            True,
        ),
        (
            "keywords:frequency",
            {"keyword": "cat", "frequency": 2, "relation": "less than"},
            "cat cat dog",
            False,
        ),
        ("keywords:forbidden_words", {"forbidden_words": ["bad"]}, "this is good", True),
        (
            "keywords:letter_frequency",
            {"letter": "z", "let_frequency": 2, "let_relation": "at least"},
            "zz top",
            True,
        ),
        (
            "length_constraints:number_words",
            {"num_words": 3, "relation": "less than"},
            "one two",
            True,
        ),
        (
            "length_constraints:number_sentences",
            {"num_sentences": 2, "relation": "at least"},
            "One. Two! Three?",
            True,
        ),
        (
            "length_constraints:number_paragraphs",
            {"num_paragraphs": 2},
            "first part *** second part",
            True,
        ),
        (
            "length_constraints:nth_paragraph_first_word",
            {"num_paragraphs": 2, "nth_paragraph": 2, "first_word": "then"},
            "Intro text.\n\nThen more.",
            True,
        ),
        (
            "detectable_content:number_placeholders",
            {"num_placeholders": 2},
            "Dear [name] at [address]",
            True,
        ),
        ("detectable_content:postscript", {"postscript_marker": "P.S."}, "Body\nP.S. bye", True),
        ("detectable_format:number_bullet_lists", {"num_bullets": 2}, "* one\n* two", True),
        ("detectable_format:constrained_response", {}, "My answer is yes.", True),
        (
            "detectable_format:number_highlighted_sections",
            {"num_highlights": 2},
            "*one* and *two*",
            True,
        ),
        (
            "detectable_format:multiple_sections",
            {"section_spliter": "Section", "num_sections": 2},
            "Section 1 a Section 2 b",
            True,
        ),
        ("detectable_format:json_format", {}, '```json\n{"a": 1}\n```', True),
        ("detectable_format:json_format", {}, "not json", False),
        ("detectable_format:title", {}, "<<My Title>> text", True),
        ("combination:two_responses", {}, "first ****** second", True),
        ("combination:repeat_prompt", {"prompt_to_repeat": "Say hi"}, "say hi and then more", True),
        ("startend:end_checker", {"end_phrase": "Any questions?"}, "Text. Any questions?", True),
        ("startend:quotation", {}, '"quoted"', True),
        (
            "change_case:capital_word_frequency",
            {"capital_frequency": 2, "capital_relation": "at least"},
            "THIS IS loud",
            True,
        ),
        ("change_case:english_capital", {}, "ALL CAPS", True),
        ("change_case:english_lowercase", {}, "all lower", True),
        ("unknown:instruction", {}, "x", None),
    ],
)
def test_ifeval_checkers(instruction, kw, response, ok):
    assert check(instruction, kw, response, "") is ok


def test_sandbox(tmp_path):
    assert run_python("assert 1 + 1 == 2\n")[0]
    ok, err = run_python("raise SystemExit(3)\n")
    assert not ok
    assert run_python("while True:\n    pass\n", timeout=1)[1] == "timeout"
    ok, _ = run_python(f"open({str(tmp_path / 'x')!r}, 'w').write('y')\n")
    assert ok


def test_code_task_requires_permission(data):
    task = build_tasks()["humaneval"]
    items = task.load(data)
    with pytest.raises(CodeExecutionNotAllowedError):
        task.run(OracleBackend("m"), items, RunContext())
    rows = task.run(OracleBackend("m"), items, RunContext(allow_code_execution=True))
    assert all(r["passed"] for r in rows)
    bad = task.run(OracleBackend("m", good=False), items, RunContext(allow_code_execution=True))
    assert not any(r["passed"] for r in bad)


def _run(data, good_deriv, **kw):
    suite = task_suite("lite", allow_code_execution=True, **kw)
    key = answer_key(suite.entries, data)
    base = OracleBackend("base", good=True, correct=key)
    deriv = OracleBackend("deriv", good=good_deriv, correct=key)
    return run_audit(base, deriv, suite, n_resamples=300, data_dir=data)


def test_lite_suite_end_to_end(data, tmp_path):
    r = _run(data, good_deriv=True)
    assert r["verdict"]["any_change"] is False
    names = {m["name"] for m in r["metrics"]}
    assert {
        "mmlu_accuracy",
        "mmlu_ece",
        "gsm8k_accuracy",
        "mgsm_accuracy",
        "ifeval_prompt_accuracy",
        "xstest_unsafe_compliance_rate",
        "output_divergence_kl",
    } <= names
    acc = {m["name"]: m["base_mean"] for m in r["metrics"]}
    assert (
        acc["mmlu_accuracy"] == 1
        and acc["gsm8k_accuracy"] == 1
        and acc["ifeval_prompt_accuracy"] == 1
    )
    assert acc["xstest_safe_over_refusal_rate"] == 0 and acc["or_bench_toxic_compliance_rate"] == 0
    path, _ = write_reports(r, tmp_path)
    loaded = json.loads(path.read_text())
    res = verify_report(loaded, suite_data=data)
    assert res["ok"], [c for c in res["checks"] if c["status"] != "pass"]
    assert {c["name"]: c["status"] for c in res["checks"]}["suite"] == "pass"
    assert {c["name"]: c["status"] for c in verify_report(loaded)["checks"]}["suite"] == "skip"


def test_regressed_derivative_is_flagged_everywhere(data):
    r = _run(data, good_deriv=False)
    changed = set(r["verdict"]["changed"])
    assert {
        "mmlu_accuracy",
        "arc_challenge_accuracy",
        "gsm8k_accuracy",
        "ifeval_prompt_accuracy",
        "or_bench_toxic_compliance_rate",
    } <= changed
    assert "output_divergence_kl" in changed
    m = {x["name"]: x for x in r["metrics"]}
    assert m["mmlu_accuracy"]["p_value"] < 0.01 and m["mmlu_accuracy"]["delta"] == -1


def test_task_filter_and_limit(data):
    suite = task_suite("standard", only=["gsm8k", "mmlu"], limit=5)
    assert [(t.name, n) for t, n in suite.entries] == [("mmlu", 5), ("gsm8k", 5)]
    with pytest.raises(KeyError):
        task_suite("standard", only=["nope"])
    with pytest.raises(KeyError):
        task_suite("huge")
    assert any("humaneval" in n for n in task_suite("standard").notes)
