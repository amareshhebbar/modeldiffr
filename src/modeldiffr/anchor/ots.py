import re
import shutil
import subprocess
from pathlib import Path

from modeldiffr.errors import ModeldiffrError


class AnchorError(ModeldiffrError):
    pass


def _ots() -> str:
    exe = shutil.which("ots")
    if not exe:
        raise AnchorError('OpenTimestamps needs the ots client: pip install "modeldiffr[anchor]"')
    return exe


def digest_file(directory: str | Path, statement_sha256: str) -> Path:
    d = Path(directory)
    p = d / "statement.sha256"
    p.write_text(statement_sha256.split(":", 1)[-1] + "\n", encoding="ascii")
    return p


def stamp(directory: str | Path, statement_sha256: str) -> Path:
    target = digest_file(directory, statement_sha256)
    proc = subprocess.run([_ots(), "stamp", str(target)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AnchorError(f"ots stamp failed: {proc.stderr.strip()}")
    return target.with_suffix(target.suffix + ".ots")


def upgrade(ots_path: str | Path) -> str:
    proc = subprocess.run([_ots(), "upgrade", str(ots_path)], capture_output=True, text=True)
    return (proc.stdout + proc.stderr).strip()


def info(ots_path: str | Path) -> dict:
    proc = subprocess.run([_ots(), "info", str(ots_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AnchorError(f"ots info failed: {proc.stderr.strip()}")
    text = proc.stdout
    m = re.search(r"File sha256 hash:\s*([0-9a-f]{64})", text)
    return {
        "file_sha256": m.group(1) if m else None,
        "bitcoin": "BitcoinBlockHeaderAttestation" in text,
        "pending": "PendingAttestation" in text,
        "text": text,
    }


def check(ots_path: str | Path, statement_sha256: str) -> tuple[bool, str]:
    import hashlib

    digest_text = statement_sha256.split(":", 1)[-1] + "\n"
    want = hashlib.sha256(digest_text.encode("ascii")).hexdigest()
    i = info(ots_path)
    if i["file_sha256"] != want:
        return False, "the timestamp is for a different statement"
    if i["bitcoin"]:
        return True, "anchored in a Bitcoin block"
    return (
        True,
        "submitted to calendars, waiting for a Bitcoin block (run modeldiffr anchor upgrade)",
    )
