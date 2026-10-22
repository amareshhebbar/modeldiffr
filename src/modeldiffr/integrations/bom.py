import uuid

NAMESPACE = uuid.UUID("6f1c1d3e-6d0b-4c7a-9a36-2f3e5f6a7b8c")


def _hex(v):
    return v.split(":", 1)[1] if v and ":" in v else v


def _model_component(side: str, entry: dict) -> dict:
    comp = {
        "type": "machine-learning-model",
        "bom-ref": side,
        "name": entry.get("model_id") or side,
        "version": entry.get("commit") or entry.get("revision") or "unknown",
        "properties": [
            {"name": "modeldiffr:role", "value": side},
            {
                "name": "modeldiffr:weights_algorithm",
                "value": entry.get("weights_algorithm") or "none",
            },
        ],
    }
    if entry.get("weights_root"):
        comp["hashes"] = [{"alg": "SHA-256", "content": _hex(entry["weights_root"])}]
    for key in ("tokenizer_vocab", "chat_template"):
        if entry.get(key):
            comp["properties"].append({"name": f"modeldiffr:{key}", "value": entry[key]})
    return comp


def cyclonedx(report: dict) -> dict:
    from modeldiffr import __version__

    m = report["manifest"]
    findings = [
        {
            "name": f"modeldiffr:metric:{x['name']}",
            "value": (
                f"delta={x['delta']:.6g} ci=[{x['ci_low']:.6g},{x['ci_high']:.6g}] "
                f"significant={x['significant']}"
            ),
        }
        for x in report["metrics"]
    ]
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(NAMESPACE, report['audit_id'])}",
        "version": 1,
        "metadata": {
            "timestamp": report["created_at"],
            "tools": {
                "components": [
                    {"type": "application", "name": "modeldiffr", "version": __version__}
                ]
            },
            "properties": [
                {"name": "modeldiffr:audit_id", "value": report["audit_id"]},
                {"name": "modeldiffr:results_root", "value": report["proof"]["results_root"]},
                {
                    "name": "modeldiffr:statement_sha256",
                    "value": report["proof"]["statement_sha256"],
                },
                {"name": "modeldiffr:suite", "value": f"{m['suite']['name']} {m['suite']['root']}"},
                {
                    "name": "modeldiffr:verdict",
                    "value": ", ".join(report["verdict"]["changed"]) or "no significant change",
                },
            ]
            + findings,
        },
        "components": [
            _model_component("base", m["base"]),
            _model_component("derivative", m["derivative"]),
        ],
        "dependencies": [
            {"ref": "derivative", "dependsOn": ["base"]},
            {"ref": "base", "dependsOn": []},
        ],
    }


def spdx(report: dict) -> dict:
    from modeldiffr import __version__

    m = report["manifest"]
    doc_id = f"https://modeldiffr.dev/spdx/{_hex(report['audit_id'])}"
    creation = {
        "type": "CreationInfo",
        "@id": "_:creation",
        "specVersion": "3.0.1",
        "created": report["created_at"],
        "createdBy": [f"{doc_id}#tool"],
    }
    graph = [
        creation,
        {
            "type": "Tool",
            "spdxId": f"{doc_id}#tool",
            "creationInfo": "_:creation",
            "name": f"modeldiffr {__version__}",
        },
    ]
    for side in ("base", "derivative"):
        e = m[side]
        pkg = {
            "type": "ai_AIPackage",
            "spdxId": f"{doc_id}#{side}",
            "creationInfo": "_:creation",
            "name": e.get("model_id") or side,
            "software_packageVersion": e.get("commit") or "unknown",
            "software_primaryPurpose": "model",
        }
        if e.get("weights_root"):
            pkg["verifiedUsing"] = [
                {"type": "Hash", "algorithm": "sha256", "hashValue": _hex(e["weights_root"])}
            ]
        graph.append(pkg)
    graph.append(
        {
            "type": "Relationship",
            "spdxId": f"{doc_id}#rel",
            "creationInfo": "_:creation",
            "from": f"{doc_id}#base",
            "relationshipType": "ancestorOf",
            "to": [f"{doc_id}#derivative"],
            "comment": f"Modeldiffr audit {report['audit_id']}: "
            + (", ".join(report["verdict"]["changed"]) or "no significant change"),
        }
    )
    graph.append(
        {
            "type": "SpdxDocument",
            "spdxId": doc_id,
            "creationInfo": "_:creation",
            "rootElement": [f"{doc_id}#derivative"],
            "element": [g["spdxId"] for g in graph if "spdxId" in g],
            "profileConformance": ["core", "software", "ai"],
        }
    )
    return {"@context": "https://spdx.org/rdf/3.0.1/spdx-context.jsonld", "@graph": graph}
