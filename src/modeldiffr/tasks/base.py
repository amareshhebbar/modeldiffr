import hashlib
from dataclasses import dataclass, field

from modeldiffr.metrics import MetricSpec
from modeldiffr.proof.canonical import canonical_json


@dataclass(frozen=True)
class Item:
    id: str
    data: dict


@dataclass(frozen=True)
class Source:
    path: str
    config: str | None = None
    split: str = "test"
    revision: str | None = None
    parquet_branch: bool = False

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "config": self.config,
            "split": self.split,
            "revision": self.revision,
        }


@dataclass
class RunContext:
    renderer: object = None
    refusal_detector: object = None
    allow_code_execution: bool = False
    progress: object = None

    def log(self, message: str) -> None:
        if self.progress:
            self.progress(message)


@dataclass
class Task:
    name: str
    kind: str
    description: str
    metrics: tuple[MetricSpec, ...]
    source: Source | None = None
    max_new_tokens: int = 0
    needs_code_execution: bool = False
    builtin_items: tuple[Item, ...] = field(default_factory=tuple)

    def convert(self, rows: list[dict]) -> list[Item]:
        raise NotImplementedError

    def load(self, data_dir=None) -> list[Item]:
        if self.builtin_items:
            return list(self.builtin_items)
        from modeldiffr.tasks.data import load_rows

        return self.convert(load_rows(self, data_dir))

    def run(self, backend, items: list[Item], ctx: RunContext) -> list[dict]:
        raise NotImplementedError

    def cost(self, n: int) -> dict:
        return {"loglik": 0, "generate": 0, "tokens": 0}

    def entry(self, items: list[Item]) -> dict:
        return {
            "name": self.name,
            "kind": self.kind,
            "source": self.source.to_dict() if self.source else {"path": "builtin"},
            "items": len(items),
            "max_new_tokens": self.max_new_tokens,
        }


def item_key(task: str, item_id: str) -> str:
    return hashlib.sha256(f"{task}\x00{item_id}".encode()).hexdigest()


def select(task: str, items: list[Item], size: int | None) -> list[Item]:
    if size is None or size >= len(items):
        return list(items)
    chosen = sorted(items, key=lambda it: item_key(task, it.id))[:size]
    order = {it.id: i for i, it in enumerate(items)}
    return sorted(chosen, key=lambda it: order[it.id])


def item_leaf_data(task: str, item: Item) -> bytes:
    return canonical_json({"task": task, "id": item.id, "data": item.data})
