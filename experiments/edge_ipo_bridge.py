"""Bridge IPO EDGE facts into the central consumer-neutral evidence backbone.

The bridge accepts only a verified READY export produced by IPO EDGE. It does not
score, grade, recommend, learn, write historical checkpoints, or trade.
"""
import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone

from experiments.data_contract import DataArchitectureError, build_record
from experiments.data_requirements import requirements
from experiments.shared_evidence_bundle import (
    build_shared_evidence_bundle,
    verify_shared_evidence_bundle,
)

EXPORT_SCHEMA="edge-ipo-shared-evidence-export-v1"
HEX64=re.compile(r"^[0-9a-f]{64}$")
ALLOWED_STATES={
    "COMPLETE","VERIFIED_PARTIAL","RECOVERED_VIA_FALLBACK"
}
FORBIDDEN_BOUNDARY_FLAGS=(
    "methodology_applied","scoring_applied","grade_assigned",
    "recommendation_generated","learning_promoted",
    "historical_checkpoint_write_enabled","trading_enabled",
)


def _aware(value, field):
    if isinstance(value,datetime):
        parsed=value
    elif isinstance(value,str):
        try:
            parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
        except ValueError:
            raise DataArchitectureError(f"{field} invalid") from None
    else:
        raise DataArchitectureError(f"{field} invalid")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataArchitectureError(f"{field} timezone missing")
    return parsed.astimezone(timezone.utc)


def _verify_export(export):
    if not isinstance(export,dict) or export.get("schema")!=EXPORT_SCHEMA:
        raise DataArchitectureError("EDGE_IPO export schema invalid")
    if export.get("consumer")!="EDGE_IPO":
        raise DataArchitectureError("EDGE_IPO export consumer invalid")
    if export.get("status")!="READY":
        raise DataArchitectureError("blocked EDGE_IPO export cannot enter shared backbone")
    for flag in FORBIDDEN_BOUNDARY_FLAGS:
        if export.get(flag) is not False:
            raise DataArchitectureError("EDGE_IPO export crossed intelligence/governance boundary")
    digest=export.get("bundle_sha256")
    if not isinstance(digest,str) or not HEX64.fullmatch(digest):
        raise DataArchitectureError("EDGE_IPO export fingerprint invalid")
    body={k:v for k,v in export.items() if k!="bundle_sha256"}
    expected=hashlib.sha256(
        json.dumps(body,sort_keys=True,separators=(",",":"),default=str).encode()
    ).hexdigest()
    if expected!=digest:
        raise DataArchitectureError("EDGE_IPO export fingerprint mismatch")
    return digest


def _composite_source(item):
    sources=item.get("sources")
    if not isinstance(sources,list) or not sources:
        raise DataArchitectureError("EDGE_IPO evidence provenance missing")
    digests=[]
    refs=[]
    semantics=[]
    for source in sources:
        if not isinstance(source,dict):
            raise DataArchitectureError("EDGE_IPO evidence source invalid")
        digest=source.get("source_sha256")
        url=source.get("url")
        source_type=source.get("source_type")
        if not isinstance(digest,str) or not HEX64.fullmatch(digest):
            raise DataArchitectureError("EDGE_IPO source digest invalid")
        if not isinstance(url,str) or not url.startswith("https://"):
            raise DataArchitectureError("EDGE_IPO source reference invalid")
        if not isinstance(source_type,str) or not source_type:
            raise DataArchitectureError("EDGE_IPO source type invalid")
        digests.append(digest)
        refs.append(url)
        semantics.append(source_type)
    return {
        "sha256":hashlib.sha256("|".join(sorted(digests)).encode()).hexdigest(),
        "reference":"IPO_EDGE_COMPOSITE:"+hashlib.sha256(
            "|".join(sorted(refs)).encode()
        ).hexdigest(),
        "source_types":sorted(set(semantics)),
        "source_urls":sorted(set(refs)),
    }


def import_edge_ipo_export(export):
    export_sha=_verify_export(export)
    subject=export.get("subject")
    if not isinstance(subject,dict):
        raise DataArchitectureError("EDGE_IPO export subject invalid")
    subject_id=subject.get("id")
    name=subject.get("name")
    segment=subject.get("segment")
    if not all(isinstance(x,str) and x.strip() for x in (subject_id,name,segment)):
        raise DataArchitectureError("EDGE_IPO subject identity invalid")
    if segment not in {"MAINBOARD","SME"}:
        raise DataArchitectureError("EDGE_IPO segment invalid")
    shared_subject={
        "kind":"IPO",
        "id":subject_id.strip(),
        "name":name.strip(),
        "segment":segment,
    }
    for optional in ("isin","symbol","exchange"):
        value=subject.get(optional)
        if value is not None:
            shared_subject[optional]=value

    frozen=_aware(export.get("frozen_at"),"EDGE_IPO export freeze")
    evidence=export.get("evidence")
    if not isinstance(evidence,list):
        raise DataArchitectureError("EDGE_IPO evidence invalid")

    allowed={row["variable_id"] for row in requirements("EDGE_IPO")}
    records=[]
    seen=set()
    state_summary={}
    for item in evidence:
        if not isinstance(item,dict):
            raise DataArchitectureError("EDGE_IPO evidence item invalid")
        variable=item.get("variable_id")
        state=item.get("status")
        if variable not in allowed:
            raise DataArchitectureError("EDGE_IPO variable outside shared registry")
        if variable in seen:
            raise DataArchitectureError("duplicate EDGE_IPO variable")
        seen.add(variable)
        if state not in ALLOWED_STATES:
            raise DataArchitectureError("unresolved EDGE_IPO evidence cannot enter READY bundle")
        values=item.get("values")
        if not isinstance(values,dict):
            raise DataArchitectureError("EDGE_IPO evidence values invalid")
        observed=_aware(item.get("observed_at"),"EDGE_IPO observation")
        source=_composite_source(item)
        records.append(build_record(
            provider_id="IPO_EDGE_RECONCILER",
            source_semantic="IPO_EDGE_GOVERNED_EVIDENCE",
            variable_id=variable,
            consumer="EDGE_IPO",
            subject=shared_subject,
            metric="governed_ipo_fact_set",
            values={
                "evidence_state":state,
                "facts":deepcopy(values),
                "source_types":source["source_types"],
                "source_urls":source["source_urls"],
                "notes":item.get("notes"),
            },
            timeframe="event_or_snapshot",
            provider_timestamp=observed,
            acquisition_timestamp=frozen,
            freshness_status="LIVE" if observed.date()==frozen.date() else "HISTORICAL",
            source_reference=source["reference"],
            source_sha256=source["sha256"],
        ))
        state_summary[variable]=state

    required={row["variable_id"] for row in requirements("EDGE_IPO")}
    if seen!=required:
        raise DataArchitectureError(
            "EDGE_IPO READY export does not match shared consumer requirements"
        )

    bundle=build_shared_evidence_bundle(
        consumer="EDGE_IPO",
        subject=shared_subject,
        run_id=export.get("run_id"),
        frozen_at=frozen,
        quantitative_records=records,
        derived_evidence={
            "schema":"edge-ipo-shared-bridge-context-v1",
            "ipo_edge_export_sha256":export_sha,
            "evidence_states":state_summary,
            "source_health":deepcopy(export.get("source_health",[])),
            "methodology_applied":False,
            "scoring_applied":False,
            "grade_assigned":False,
            "recommendation_generated":False,
            "learning_promoted":False,
        },
        required_variables=required,
        require_screenshot_free=True,
    )
    if bundle["status"]!="READY":
        raise DataArchitectureError("EDGE_IPO shared bundle unexpectedly blocked")
    verify_shared_evidence_bundle(bundle)
    return bundle


def verify_edge_ipo_shared_bundle(bundle):
    summary=verify_shared_evidence_bundle(bundle)
    if summary["consumer"]!="EDGE_IPO":
        raise DataArchitectureError("EDGE_IPO shared bundle consumer mismatch")
    ctx=bundle.get("derived_evidence")
    if not isinstance(ctx,dict) or ctx.get("schema")!="edge-ipo-shared-bridge-context-v1":
        raise DataArchitectureError("EDGE_IPO bridge context invalid")
    for flag in (
        "methodology_applied","scoring_applied","grade_assigned",
        "recommendation_generated","learning_promoted",
    ):
        if ctx.get(flag) is not False:
            raise DataArchitectureError("EDGE_IPO bridge crossed intelligence boundary")
    return summary
