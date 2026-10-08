"""ASCENT G1 controlled research evidence producer/consumer integration test.
Exa/ChatGPT-curated fixed fixture; this runner does NOT invoke Exa or ChatGPT APIs.
DB test writes ONLY new, fenced G1 tables. No existing data mutated, no orders.
"""
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from src.engine_contract import EngineRequest, EvidenceItem, validate_engine_request

FIXTURE=Path("experiments/g1_research_fixtures/rbi_2026-10-07.json")
ROOT=Path(".g1")
DATA=ROOT/"research-evidence.json"
COMMIT=ROOT/"research-manifest-commit.json"
ACK=ROOT/"research-consumer-ack.json"

class ResearchGate(Exception):
    pass

def sha(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()).hexdigest()

def load_fixture():
    record=json.loads(FIXTURE.read_text(encoding="utf-8"))
    if record.get("schema")!="ascent-n3-g1-research-fixture-v1":
        raise ResearchGate("SCHEMA_BAD")
    if record.get("source",{}).get("authority")!="Reserve Bank of India":
        raise ResearchGate("PRIMARY_AUTHORITY_BAD")
    if record["source"].get("url")!="https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=63742":
        raise ResearchGate("SOURCE_URL_BAD")
    day=date.fromisoformat(record["as_of_ist_date"])
    published=date.fromisoformat(record["source"]["published_date"])
    event=date.fromisoformat(record["source"]["event_date"])
    if published>day or event>day:
        raise ResearchGate("FUTURE_FACT_LEAK")
    for c in record.get("cross_checks",[]):
        if date.fromisoformat(c["published_date"])>day:
            raise ResearchGate("LATE_CORROBORATION")
    f=record["extracted_fact"]
    if f["event_type"]!="MONETARY_POLICY_DECISION":
        raise ResearchGate("EVENT_TYPE_BAD")
    if abs(f["repo_rate_before_percent"]+f["rate_increase_basis_points"]/100-f["repo_rate_after_percent"])>1e-8:
        raise ResearchGate("RATE_ARITHMETIC_BAD")
    if record["chatgpt_analysis"]["directional_claim"]!="NO_DETERMINISTIC_NIFTY_DIRECTION":
        raise ResearchGate("DIRECTIONAL_LEAK")
    if any(record["safety"].values()):
        raise ResearchGate("EVIDENCE_SIDE_EFFECTS_FORBIDDEN")
    return record

def connection():
    import psycopg
    url=os.getenv("DATABASE_URL","")
    if not url:
        raise ResearchGate("DB_CONFIG_NOT_AVAILABLE")
    try:
        return psycopg.connect(url,connect_timeout=15)
    except Exception:
        raise ResearchGate("DB_CONNECTION_FAILED") from None

def produce():
    from psycopg.types.json import Jsonb
    record=load_fixture()
    run=os.getenv("GITHUB_RUN_ID","")
    if not run or not run.isdigit():
        raise ResearchGate("RUN_ID_ABSENT")
    manifest={
        "schema":"ascent-n3-g1-manual-exa-chatgpt-bridge-v1",
        "run_id":run,"event_date":record["source"]["event_date"],
        "source_url":record["source"]["url"],
        "source_published_date":record["source"]["published_date"],
        "captured_at_utc":datetime.now(timezone.utc).isoformat(),
        "source_precision":"DATE_ONLY",
        "method":"Exa + ChatGPT in a supervised chat; frozen validated structured fixture",
        "research":record,"trade_execution_enabled":False,
        "production_forecast_enabled":False}
    digest=sha(manifest)
    ROOT.mkdir(exist_ok=True)
    DATA.write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding="utf-8")
    try:
        with connection() as db:
            with db.cursor() as cur:
                cur.execute("CREATE SCHEMA IF NOT EXISTS ascent_n3_g1_evidence")
                cur.execute("""CREATE TABLE IF NOT EXISTS ascent_n3_g1_evidence.research_manifests (
                    run_id TEXT PRIMARY KEY, digest_sha256 TEXT NOT NULL,
                    payload JSONB NOT NULL, committed_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
                cur.execute("""CREATE TABLE IF NOT EXISTS ascent_n3_g1_evidence.research_consumer_acks (
                    run_id TEXT PRIMARY KEY REFERENCES ascent_n3_g1_evidence.research_manifests(run_id),
                    digest_sha256 TEXT NOT NULL, acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
                cur.execute("""INSERT INTO ascent_n3_g1_evidence.research_manifests
                    (run_id, digest_sha256, payload) VALUES (%s,%s,%s)
                    ON CONFLICT(run_id) DO NOTHING""",(run,digest,Jsonb(manifest)))
                cur.execute("""SELECT digest_sha256 FROM ascent_n3_g1_evidence.research_manifests
                    WHERE run_id=%s""",(run,))
                row=cur.fetchone()
                if not row or row[0]!=digest:
                    raise ResearchGate("IMMUTABLE_CONFLICT")
        COMMIT.write_text(json.dumps({"run_id":run,"digest_sha256":digest,"state":"COMMITTED",
            "source_type":"SUPERVISED_EXA_CHATGPT"}),encoding="utf-8")
        print("G1_RESEARCH_PRODUCER=COMMITTED")
        return 0
    except ResearchGate:
        raise
    except Exception:
        raise ResearchGate("DB_COMMIT_FAILED") from None

def consume():
    run=os.getenv("GITHUB_RUN_ID","")
    if not COMMIT.is_file():
        raise ResearchGate("COMMIT_RECEIPT_MISSING")
    ptr=json.loads(COMMIT.read_text())
    if ptr["run_id"]!=run or ptr["state"]!="COMMITTED":
        raise ResearchGate("COMMIT_RUN_ID_MISMATCH")
    try:
        with connection() as db:
            with db.cursor() as cur:
                cur.execute("""SELECT digest_sha256,payload
                    FROM ascent_n3_g1_evidence.research_manifests WHERE run_id=%s""",(run,))
                row=cur.fetchone()
                if not row:
                    raise ResearchGate("NOT_DURABLE")
                digest, data=row
                if digest!=ptr["digest_sha256"] or sha(data)!=digest or data["run_id"]!=run:
                    raise ResearchGate("RESEARCH_HASH_MISMATCH")
                if data["trade_execution_enabled"] is not False or data["production_forecast_enabled"] is not False:
                    raise ResearchGate("RESEARCH_SIDE_EFFECT_BLOCK")
                if data["research"]["source"]["url"]!=data["source_url"]:
                    raise ResearchGate("RESEARCH_SOURCE_MISMATCH")
                request=EngineRequest(
                    request_id=run,
                    provenance_mode="AUTOMATED",
                    evidence=[EvidenceItem(
                        evidence_type="ASCENT_N3_G1_RESEARCH_EXA_CHATGPT_PROOF",
                        source_ref="research:sha256="+digest,
                        captured_at=data["captured_at_utc"],
                        normalized={"event_type":data["research"]["extracted_fact"]["event_type"],
                                    "repo_rate_percent":data["research"]["extracted_fact"]["repo_rate_after_percent"],
                                    "published_date":data["source_published_date"],
                                    "nifty_impact_status":"QUALITATIVE_NOT_SCORED",
                                    "evidence_hash":digest})])
                if not validate_engine_request(request):
                    raise ResearchGate("ENGINE_CONTRACT_REJECTED")
                cur.execute("""INSERT INTO ascent_n3_g1_evidence.research_consumer_acks
                    (run_id,digest_sha256) VALUES(%s,%s) ON CONFLICT(run_id) DO NOTHING""",(run,digest))
                cur.execute("""SELECT digest_sha256 FROM ascent_n3_g1_evidence.research_consumer_acks
                    WHERE run_id=%s""",(run,))
                ack=cur.fetchone()
                if not ack or ack[0]!=digest:
                    raise ResearchGate("ACK_INCONSISTENT")
        ACK.write_text(json.dumps({"run_id":run,"digest_sha256":digest,
            "ack":"PASS_DB_COMMIT_AND_ENGINE_CONTRACT",
            "consumer":"LEGACY_5DR_ENGINE_REQUEST_PRECHECK_ONLY",
            "n3_full_engine_release":"NOT_PROVEN","trading_enabled":False},sort_keys=True),encoding="utf-8")
        print("G1_RESEARCH_CONSUMER=ACK_VERIFIED")
        print("G1_ENGINE_CONTRACT=VALIDATED_NO_FORECAST")
        return 0
    except ResearchGate:
        raise
    except Exception:
        raise ResearchGate("READBACK_OR_ACK_FAILED") from None

def main():
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("produce","consume"):
            raise ResearchGate("PHASE_INVALID")
        return produce() if sys.argv[1]=="produce" else consume()
    except ResearchGate as exc:
        print("G1_RESEARCH=BLOCKED:"+str(exc))
        return 1

if __name__=="__main__":
    raise SystemExit(main())
