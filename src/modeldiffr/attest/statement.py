STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://modeldiffr.dev/attestation/audit/v1"
PAYLOAD_TYPE = "application/vnd.in-toto+json"


def _hex(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(":", 1)[1] if ":" in value else value


def build_statement(report: dict) -> dict:
    manifest = report["manifest"]
    subjects = []
    for side in ("base", "derivative"):
        root = _hex(manifest[side].get("weights_root"))
        if root:
            subjects.append(
                {"name": f"{side}:{manifest[side].get('model_id')}", "digest": {"sha256": root}}
            )
    subjects.append({"name": "modeldiffr:audit", "digest": {"sha256": _hex(report["audit_id"])}})
    metrics = [
        {
            k: m.get(k)
            for k in ("name", "delta", "ci_low", "ci_high", "p_value", "significant", "negligible")
            if k in m
        }
        for m in report["metrics"]
    ]
    predicate = {
        "audit_id": report["audit_id"],
        "schema_version": report["schema_version"],
        "modeldiffr_version": report["modeldiffr_version"],
        "created_at": report["created_at"],
        "base": manifest["base"],
        "derivative": manifest["derivative"],
        "suite": {"name": manifest["suite"]["name"], "root": manifest["suite"]["root"]},
        "results_root": report["proof"]["results_root"],
        "statement_sha256": report["proof"]["statement_sha256"],
        "verdict": report["verdict"],
        "metrics": metrics,
    }
    return {
        "_type": STATEMENT_TYPE,
        "subject": subjects,
        "predicateType": PREDICATE_TYPE,
        "predicate": predicate,
    }


def check_binding(statement: dict, report: dict) -> list[str]:
    problems = []
    if statement.get("_type") != STATEMENT_TYPE:
        problems.append("not an in toto v1 statement")
    if statement.get("predicateType") != PREDICATE_TYPE:
        problems.append("not a Modeldiffr audit attestation")
    p = statement.get("predicate") or {}
    for key, want in (
        ("audit_id", report["audit_id"]),
        ("results_root", report["proof"]["results_root"]),
        ("statement_sha256", report["proof"]["statement_sha256"]),
    ):
        if p.get(key) != want:
            problems.append(f"signed {key} does not match the report")
    if p.get("verdict") != report["verdict"]:
        problems.append("signed verdict does not match the report")
    return problems
