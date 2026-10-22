import re
from pathlib import Path
from urllib.parse import quote

HUB = "https://huggingface.co"
FILES = (
    "report.json",
    "report.html",
    "report.dsse.json",
    "report.sigstore.json",
    "statement.sha256.ots",
    "anchors.json",
    "bom.cdx.json",
)


def parse_model_ref(ref: str) -> tuple[str, str | None]:
    m = re.match(r"^https?://huggingface\.co/([^/]+/[^/@]+)(?:/tree/([^/]+))?/?$", ref)
    if m:
        return m.group(1), m.group(2)
    return ref, None


def badge(report: dict, link: str) -> str:
    v = report["verdict"]
    if v["changed"]:
        label, color = f"{len(v['changed'])} changed", "b3261e"
    else:
        label, color = "no significant change", "1f7a4d"
    text = quote(label.replace("-", "--").replace("_", "__"), safe="")
    return f"[![Modeldiffr audit](https://img.shields.io/badge/modeldiffr-{text}-{color})]({link})"


def push(
    report_dir: str | Path, repo_id: str, report: dict, token: str | None = None, api=None
) -> dict:
    if api is None:
        from huggingface_hub import HfApi

        api = HfApi(token=token)
    d = Path(report_dir)
    short = report["audit_id"].split(":", 1)[1][:16]
    path_in_repo = f"modeldiffr/{short}"
    allow = [f for f in FILES if (d / f).exists()]
    api.upload_folder(
        folder_path=str(d),
        repo_id=repo_id,
        path_in_repo=path_in_repo,
        allow_patterns=allow,
        commit_message=f"Add Modeldiffr audit {short}",
    )
    url = f"{HUB}/{repo_id}/blob/main/{path_in_repo}/report.html"
    return {
        "repo": repo_id,
        "path": path_in_repo,
        "files": allow,
        "url": url,
        "badge": badge(report, url),
    }
