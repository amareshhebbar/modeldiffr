from dataclasses import dataclass, field

from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Source, Task
from modeldiffr.tasks.code import HumanEval, code_metric
from modeldiffr.tasks.divergence import DivergenceTask, divergence_metric
from modeldiffr.tasks.generation import GSM8K, MGSM, Needle, math_metric
from modeldiffr.tasks.ifeval import IFEval, ifeval_metric
from modeldiffr.tasks.multiple_choice import ARC, MMLU, HellaSwag, TruthfulQAMC1, mc_metrics
from modeldiffr.tasks.refusal import ORBench, XSTest, compliance_metric, over_refusal_metric


def _mmlu():
    return MMLU(
        "mmlu",
        "multiple_choice",
        "MMLU, 57 subjects.",
        mc_metrics("mmlu", "MMLU"),
        Source("cais/mmlu", "all", "test", "c30699e8356da336a370243923dbaf21066bb9fe"),
    )


def build_tasks() -> dict[str, Task]:
    mmlu = _mmlu()
    tasks: list[Task] = [
        mmlu,
        ARC(
            "arc_challenge",
            "multiple_choice",
            "ARC Challenge science questions.",
            mc_metrics("arc_challenge", "ARC Challenge"),
            Source(
                "allenai/ai2_arc",
                "ARC-Challenge",
                "test",
                "210d026faf9955653af8916fad021475a3f00453",
            ),
        ),
        HellaSwag(
            "hellaswag",
            "multiple_choice",
            "HellaSwag common sense completion.",
            mc_metrics("hellaswag", "HellaSwag"),
            Source(
                "Rowan/hellaswag",
                "default",
                "validation",
                "218ec52e09a7e7462a5400043bb9a69a41d06b76",
                parquet_branch=True,
            ),
        ),
        TruthfulQAMC1(
            "truthfulqa_mc1",
            "multiple_choice",
            "TruthfulQA, single correct answer.",
            mc_metrics("truthfulqa_mc1", "TruthfulQA MC1"),
            Source(
                "truthfulqa/truthful_qa",
                "multiple_choice",
                "validation",
                "741b8276f2d1982aa3d5b832d3ee81ed3b896490",
            ),
        ),
        GSM8K(
            "gsm8k",
            "generation",
            "Grade school math word problems.",
            math_metric("gsm8k", "GSM8K"),
            Source("openai/gsm8k", "main", "test", "740312add88f781978c0658806c59bc2815b9866"),
            max_new_tokens=384,
        ),
        MGSM(
            "mgsm",
            "generation",
            "GSM8K problems translated into ten languages.",
            math_metric("mgsm", "MGSM"),
            Source(
                "juletxara/mgsm",
                "*",
                "test",
                "b2f13d426afe3be8d69a7e739b36724db8b66bbc",
                parquet_branch=True,
            ),
            max_new_tokens=384,
        ),
        IFEval(
            "ifeval",
            "instructions",
            "Verifiable formatting instructions.",
            ifeval_metric("ifeval"),
            Source("google/IFEval", None, "train", "966cd89545d6b6acfd7638bc708b98261ca58e84"),
            max_new_tokens=512,
        ),
        XSTest(
            "xstest_safe",
            "refusal",
            "XSTest harmless prompts that look sensitive.",
            over_refusal_metric("xstest_safe", "XSTest"),
            Source(
                "natolambert/xstest-v2-copy",
                None,
                "prompts",
                "b71afe2a6d10e5a6254ea8bcb006c48b095a15d5",
            ),
            max_new_tokens=96,
        ),
        ORBench(
            "or_bench_hard",
            "refusal",
            "OR Bench hard harmless prompts.",
            over_refusal_metric("or_bench_hard", "OR Bench hard"),
            Source(
                "bench-llm/or-bench",
                "or-bench-hard-1k",
                "train",
                "e36d8b80e81837c8a8f264bbb2a49f1b32c7e272",
            ),
            max_new_tokens=96,
        ),
        XSTest(
            "xstest_unsafe",
            "refusal",
            "XSTest unsafe contrast prompts.",
            compliance_metric("xstest_unsafe", "XSTest unsafe"),
            Source(
                "natolambert/xstest-v2-copy",
                None,
                "prompts",
                "b71afe2a6d10e5a6254ea8bcb006c48b095a15d5",
            ),
            max_new_tokens=96,
        ),
        ORBench(
            "or_bench_toxic",
            "refusal",
            "OR Bench toxic prompts that should be refused.",
            compliance_metric("or_bench_toxic", "OR Bench toxic"),
            Source(
                "bench-llm/or-bench",
                "or-bench-toxic",
                "train",
                "e36d8b80e81837c8a8f264bbb2a49f1b32c7e272",
            ),
            max_new_tokens=96,
        ),
        HumanEval(
            "humaneval",
            "code",
            "Python function completion checked by unit tests.",
            code_metric("humaneval"),
            Source(
                "openai/openai_humaneval",
                "openai_humaneval",
                "test",
                "7dce6050a7d6d172f3cc5c32aa97f52fa1a2e544",
            ),
            max_new_tokens=384,
            needs_code_execution=True,
        ),
        Needle(
            "needle",
            "generation",
            "Find a code hidden in a long document.",
            (
                MetricSpec(
                    "needle_accuracy",
                    "Share of long documents where the hidden code is found.",
                    "needle",
                    min_effect=0.02,
                ),
            ),
            max_new_tokens=16,
        ),
    ]
    for t in tasks:
        if t.name in ("xstest_unsafe", "or_bench_toxic"):
            t.expect_refusal = True
    div = DivergenceTask(
        "divergence",
        "divergence",
        "Neutral text: built in sentences and MMLU questions.",
        divergence_metric(),
    )
    from modeldiffr.suites import QUICK

    div.extra_texts = tuple(QUICK.neutral_texts)
    div.text_task = mmlu
    tasks.append(div)
    return {t.name: t for t in tasks}


SIZES = {
    "lite": {
        "mmlu": 200,
        "arc_challenge": 100,
        "hellaswag": 100,
        "truthfulqa_mc1": 100,
        "gsm8k": 50,
        "mgsm": 50,
        "ifeval": 50,
        "xstest_safe": 50,
        "or_bench_hard": 50,
        "xstest_unsafe": 50,
        "or_bench_toxic": 50,
        "divergence": 50,
    },
    "standard": {
        "mmlu": 1000,
        "arc_challenge": 500,
        "hellaswag": 500,
        "truthfulqa_mc1": None,
        "gsm8k": 250,
        "mgsm": 250,
        "ifeval": 200,
        "xstest_safe": None,
        "or_bench_hard": 250,
        "xstest_unsafe": None,
        "or_bench_toxic": 200,
        "humaneval": 100,
        "needle": 20,
        "divergence": 200,
    },
    "full": {
        "mmlu": None,
        "arc_challenge": None,
        "hellaswag": None,
        "truthfulqa_mc1": None,
        "gsm8k": None,
        "mgsm": None,
        "ifeval": None,
        "xstest_safe": None,
        "or_bench_hard": None,
        "xstest_unsafe": None,
        "or_bench_toxic": None,
        "humaneval": None,
        "needle": None,
        "divergence": 1000,
    },
}


@dataclass
class TaskSuite:
    name: str
    entries: list[tuple[Task, int | None]]
    notes: tuple[str, ...] = field(default_factory=tuple)
    allow_code_execution: bool = False


def task_suite(
    name: str,
    only: list[str] | None = None,
    limit: int | None = None,
    allow_code_execution: bool = False,
) -> TaskSuite:
    from modeldiffr.suites import SUITES
    from modeldiffr.tasks.builtin import legacy_tasks

    if name in SUITES:
        legacy = SUITES[name]
        tasks = legacy_tasks(legacy)
        entries = [(t, limit) for t in tasks if not only or t.name in only]
        return TaskSuite(name, entries, tuple(legacy.notes))
    if name not in SIZES:
        raise KeyError(f"unknown suite {name!r}; available: {', '.join(available_suites())}")
    tasks = build_tasks()
    unknown = [t for t in only or [] if t not in tasks]
    if unknown:
        raise KeyError(f"unknown task {', '.join(unknown)}; available: {', '.join(sorted(tasks))}")
    notes = []
    entries = []
    for task_name, size in SIZES[name].items():
        if only and task_name not in only:
            continue
        task = tasks[task_name]
        if task.needs_code_execution and not allow_code_execution:
            notes.append(
                f"{task_name} skipped: it runs model written code, "
                "enable with --allow-code-execution."
            )
            continue
        if limit is not None:
            size = limit if size is None else min(size, limit)
        entries.append((task, size))
    return TaskSuite(name, entries, tuple(notes), allow_code_execution)


def available_suites() -> list[str]:
    from modeldiffr.suites import SUITES

    return sorted(SUITES) + list(SIZES)
