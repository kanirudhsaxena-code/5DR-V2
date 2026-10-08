"""ASCENT N3 G1: source manifest -> atomic DB commit -> independent consumer ACK.

This is a fenced G1 integration proof, NOT a production forecast or trading
pipeline. It only creates/inserts immutable records inside an isolated schema.
No DROP, DELETE, UPDATE, orders, broker credentials or existing market tables.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

SCHEMA="ascent_n3_g1_evidence"
SOURCES=("evidence.json","freshness.json","depth-retention.json")
POINTER=Path(".g1/manifest-pointer.json")
ACK=Path(".g1/handoff-ack.json")

class G1DBError(Exception):
    pass

def digest(obj):
    return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()

def source_manifest(run):
    lanes={}
    for filename in SOURCES:
        p=Path(".g1")/filename
        if not p.is_file():
            raise G1DBError("SOURCE_FILE_MISSING")
        try:
            data=json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise G1DBError("SOURCE_JSON_INVALID")
        if data.get("run_id")!=run or data.get("read_only") is not True or data.get("trading_enabled") is not False:
            raise G1DBError("SOURCE_PROVENANCE_MISMATCH")
        if len(data.get("receipts",[]))<2 or not isinstance(data.get("stages"),dict):
            raise G1DBError("SOURCE_UNVALIDATED")
        for receipt in data["receipts"]:
            sha=receipt.get("payload_sha256")
            if not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
                raise G1DBError("SOURCE_RECEIPT_DIGEST_MISSING")
        lanes[filename]=data
    return {"schema":"ascent-n3-g1-immutable-manifest-v1",
            "run_id":run,"source_count":len(lanes),
            "read_only":True,"trading_enabled":False,"lanes":lanes}

def conn():
    url=os.environ.get("DATABASE_URL","")
    if not url:
        raise G1DBError("EXISTING_DATABASE_SECRET_UNAVAILABLE")
    try:
        import psycopg
        return psycopg.connect(url,connect_timeout=15)
    except Exception:
        raise G1DBError("DATABASE_CONNECT_FAILED") from None

def producer(run):
    m=source_manifest(run)
    h=digest(m)
    try:
        from psycopg.types.json import Jsonb
        with conn() as db:
            with db.cursor() as c:
                c.execute("CREATE SCHEMA IF NOT EXISTS ascent_n3_g1_evidence")
                c.execute("""CREATE TABLE IF NOT EXISTS ascent_n3_g1_evidence.manifests(
                    run_id TEXT PRIMARY KEY,
                    digest_sha256 TEXT NOT NULL,
                    typed_manifest JSONB NOT NULL,
                    committed_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
                c.execute("""CREATE TABLE IF NOT EXISTS ascent_n3_g1_evidence.consumer_acks(
                    run_id TEXT PRIMARY KEY REFERENCES ascent_n3_g1_evidence.manifests(run_id),
                    digest_sha256 TEXT NOT NULL,
                    acknowledged_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
                c.execute("""INSERT INTO ascent_n3_g1_evidence.manifests(run_id,digest_sha256,typed_manifest)
                    VALUES(%s,%s,%s) ON CONFLICT(run_id) DO NOTHING""",(run,h,Jsonb(m)))
                c.execute("SELECT digest_sha256 FROM ascent_n3_g1_evidence.manifests WHERE run_id=%s",(run,))
                row=c.fetchone()
                if row is None or row[0]!=h:
                    raise G1DBError("IMMUTABILITY_CONFLICT")
        # with conn() committed on exit; pointer is written ONLY after commit.
        POINTER.parent.mkdir(parents=True,exist_ok=True)
        POINTER.write_text(json.dumps({"run_id":run,"digest_sha256":h,"source_count":len(SOURCES),
                                       "state":"COMMITTED"},sort_keys=True),encoding="utf-8")
        print("G1_MANIFEST_PRODUCER=COMMITTED")
        return 0
    except G1DBError:
        raise
    except Exception:
        raise G1DBError("ATOMIC_COMMIT_FAILED") from None

def consumer(run):
    if not POINTER.is_file():
        raise G1DBError("COMMIT_POINTER_MISSING")
    try:
        pointer=json.loads(POINTER.read_text(encoding="utf-8"))
        if pointer["run_id"]!=run or pointer["state"]!="COMMITTED":
            raise G1DBError("RUN_ID_MISMATCH")
        with conn() as db:
            with db.cursor() as c:
                c.execute("SELECT digest_sha256,typed_manifest FROM ascent_n3_g1_evidence.manifests WHERE run_id=%s",(run,))
                row=c.fetchone()
                if not row:
                    raise G1DBError("MANIFEST_NOT_COMMITTED")
                actual,manifest=row
                if (actual!=pointer["digest_sha256"] or digest(manifest)!=actual
                    or manifest.get("run_id")!=run or manifest.get("source_count")!=3
                    or manifest.get("read_only") is not True):
                    raise G1DBError("CONSUMER_HASH_RUN_MISMATCH")
                c.execute("""INSERT INTO ascent_n3_g1_evidence.consumer_acks(run_id,digest_sha256)
                    VALUES(%s,%s) ON CONFLICT(run_id) DO NOTHING""",(run,actual))
                c.execute("SELECT digest_sha256 FROM ascent_n3_g1_evidence.consumer_acks WHERE run_id=%s",(run,))
                ack=c.fetchone()
                if not ack or ack[0]!=actual:
                    raise G1DBError("CONSUMER_ACK_MISMATCH")
        ACK.write_text(json.dumps({"run_id":run,"digest_sha256":actual,
                                   "consumer":"ISOLATED_G1_PROOF_CONSUMER","ack":"VERIFIED_COMMITTED",
                                   "trading_enabled":False},sort_keys=True),encoding="utf-8")
        print("G1_MANIFEST_CONSUMER=ACK_VERIFIED")
        return 0
    except G1DBError:
        raise
    except Exception:
        raise G1DBError("CONSUMER_ATOMIC_READ_FAILED") from None

def main():
    run=os.environ.get("GITHUB_RUN_ID","")
    if not run:
        print("G1_DB=BLOCKED:RUN_ID_MISSING")
        return 1
    try:
        if len(sys.argv)!=2 or sys.argv[1] not in ("produce","consume"):
            raise G1DBError("UNRECOGNIZED_PHASE")
        return producer(run) if sys.argv[1]=="produce" else consumer(run)
    except G1DBError as exc:
        print("G1_DB=BLOCKED:"+str(exc))
        return 1

if __name__=="__main__":
    raise SystemExit(main())
