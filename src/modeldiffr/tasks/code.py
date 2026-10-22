import os
import subprocess
import sys
import tempfile

from modeldiffr.metrics import MetricSpec
from modeldiffr.tasks.base import Item, Task
from modeldiffr.tasks.runtime import generate

STOP = ("\ndef ", "\nclass ", "\nif __name__", "\nprint(", "\n#", "\nassert ")


class CodeExecutionNotAllowedError(RuntimeError):
    pass


def _limits():
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        resource.setrlimit(resource.RLIMIT_FSIZE, (16 << 20, 16 << 20))
    except Exception:
        pass


def run_python(program: str, timeout: float = 10.0) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "candidate.py")
        with open(path, "w", encoding="utf-8") as f:
            f.write(program)
        env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": tmp}
        try:
            proc = subprocess.run(
                [sys.executable, "-I", path],
                cwd=tmp,
                env=env,
                capture_output=True,
                timeout=timeout,
                preexec_fn=_limits if os.name == "posix" else None,
                stdin=subprocess.DEVNULL,
            )
        except subprocess.TimeoutExpired:
            return False, "timeout"
        return proc.returncode == 0, proc.stderr.decode("utf-8", "replace")[-500:]


class HumanEval(Task):
    def convert(self, rows):
        return [
            Item(
                r["task_id"],
                {"prompt": r["prompt"], "test": r["test"], "entry_point": r["entry_point"]},
            )
            for r in rows
        ]

    def run(self, backend, items, ctx):
        if not ctx.allow_code_execution:
            raise CodeExecutionNotAllowedError(
                "humaneval runs model written code; pass --allow-code-execution to enable it"
            )
        outs = generate(
            backend,
            [it.data["prompt"] for it in items],
            self.max_new_tokens,
            ctx,
            raw=True,
            stop=STOP,
        )
        rows = []
        for it, (completion, h) in zip(items, outs, strict=True):
            program = (
                it.data["prompt"]
                + completion
                + "\n\n"
                + it.data["test"]
                + f"\n\ncheck({it.data['entry_point']})\n"
            )
            ok, err = run_python(program)
            rows.append(
                {
                    "id": it.id,
                    "rendered_sha256": h,
                    "completion": completion,
                    "passed": ok,
                    "error": "" if ok else err,
                    "score": float(ok),
                }
            )
        return rows

    def cost(self, n):
        return {"loglik": 0, "generate": n, "tokens": n * self.max_new_tokens}


def code_metric(task):
    return (
        MetricSpec(
            f"{task}_pass_at_1",
            "Share of problems whose greedy completion passes the tests.",
            task,
            min_effect=0.01,
        ),
    )
