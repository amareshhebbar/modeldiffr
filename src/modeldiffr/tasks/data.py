import json
import os
from pathlib import Path


class DatasetUnavailableError(RuntimeError):
    pass


def _local(task, data_dir) -> list[dict] | None:
    roots = [data_dir] if data_dir else []
    if os.environ.get("MODELDIFFR_DATA_DIR"):
        roots.append(os.environ["MODELDIFFR_DATA_DIR"])
    for root in roots:
        for suffix in (".jsonl", ".json"):
            p = Path(root) / f"{task.name}{suffix}"
            if p.exists():
                text = p.read_text(encoding="utf-8")
                if suffix == ".json":
                    return json.loads(text)
                return [json.loads(line) for line in text.splitlines() if line.strip()]
    return None


def load_rows(task, data_dir=None) -> list[dict]:
    local = _local(task, data_dir)
    if local is not None:
        return local
    if data_dir:
        raise DatasetUnavailableError(f"{task.name}.jsonl is not in {data_dir}")
    src = task.source
    try:
        import datasets
    except ImportError as exc:
        raise DatasetUnavailableError(
            f'task {task.name} needs the datasets package: pip install "modeldiffr[tasks]"'
        ) from exc
    revision = "refs/convert/parquet" if src.parquet_branch else src.revision
    kwargs = {"split": src.split, "revision": revision}
    try:
        if src.parquet_branch:
            files = f"{src.config}/{src.split}/*.parquet"
            ds = datasets.load_dataset(src.path, data_files={src.split: files}, **kwargs)
        elif src.config:
            ds = datasets.load_dataset(src.path, src.config, **kwargs)
        else:
            ds = datasets.load_dataset(src.path, **kwargs)
    except Exception as exc:
        raise DatasetUnavailableError(
            f"could not load {src.path} for task {task.name}: {exc}. "
            f"Put a {task.name}.jsonl file in --data-dir to run offline."
        ) from exc
    return [dict(r) for r in ds]
