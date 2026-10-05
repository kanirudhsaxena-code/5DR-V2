"""Acquire BT100 core quantitative history into an isolated filesystem artifact.

Scope: standard historical-candle APIs only. Excludes expired instruments, market
information analytics, production databases, inference and trading.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path

from experiments.participation_universe import approved_participation_universe
from experiments.upstox_catalog import PublicInstrumentCatalog
from experiments.upstox_history_policy import plan_history_chunks
from experiments.upstox_instruments import GLOBAL_TARGET_NAMES, resolve_global_instruments
from experiments.upstox_quant_client import INDIA_VIX, QuantReadOnlyClient
from phase1.upstox import NIFTY, PipelineError


def _sha(value):
    raw=json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _frozen_window(path):
    doc=json.loads(Path(path).read_text(encoding="utf-8"))
    seq=doc.get("session_sequence")
    if not isinstance(seq,list) or len(seq)!=104:
        raise PipelineError("frozen BT100 session sequence invalid")
    return date.fromisoformat(seq[0]), date.fromisoformat(seq[-1])


def _ranges(first_target,last_outcome,lookback_days,unit,interval):
    start=first_target-timedelta(days=lookback_days)
    return plan_history_chunks(start,last_outcome,unit,interval)


def _fetch_series(client,key,timeframe,chunks):
    seen={}
    provenance=[]
    for chunk in chunks:
        envelope=client.historical(key,chunk["unit"],chunk["interval"],chunk["start"],chunk["end"])
        rows=envelope["payload"]["data"]["candles"]
        provenance.append({
            "source_path":envelope["source_path"],
            "parameters":envelope["parameters"],
            "response_sha256":envelope["sha256"],
            "validated_candles":envelope["validated_candles"],
        })
        for row in rows:
            stamp=row[0]
            prior=seen.get(stamp)
            if prior is not None and prior!=row:
                raise PipelineError(f"conflicting duplicate candle for {key} {timeframe} {stamp}")
            seen[stamp]=row
    candles=[seen[k] for k in sorted(seen)]
    if not candles:
        raise PipelineError(f"empty combined history for {key} {timeframe}")
    document={
        "schema":"bt100-core-history-series-v1",
        "instrument_key":key,
        "timeframe":timeframe,
        "candles":candles,
        "provenance":provenance,
        "production_writes":0,
        "production_neuron_calls":0,
        "trading_enabled":False,
    }
    document["series_sha256"]=_sha(document)
    return document


def run(token,frozen_sessions,output_dir):
    first,last=_frozen_window(frozen_sessions)
    catalog=PublicInstrumentCatalog()
    global_doc=catalog.global_instruments()
    globals_map=resolve_global_instruments(global_doc["records"])
    participation=approved_participation_universe()

    global_keys={name:row["instrument_key"] for name,row in globals_map.items()}
    participation_keys=list(participation.heavyweight_keys)+list(participation.sector_index_keys)
    approved={NIFTY,INDIA_VIX,*global_keys.values(),*participation_keys}
    client=QuantReadOnlyClient(token,approved)

    tasks=[]
    for tf,unit,interval,lookback in [
        ("5m","minutes",5,30),("15m","minutes",15,180),("30m","minutes",30,180),
        ("1h","hours",1,365),("1d","days",1,365),
    ]:
        tasks.append(("NIFTY_PRICE_CANDLES",NIFTY,tf,_ranges(first,last,lookback,unit,interval)))

    for tf,unit,interval,lookback in [("1h","hours",1,365),("1d","days",1,365)]:
        tasks.append(("INDIA_VIX",INDIA_VIX,tf,_ranges(first,last,lookback,unit,interval)))

    for label,key in sorted(global_keys.items()):
        for tf,unit,interval,lookback in [("1h","hours",1,365),("1d","days",1,365)]:
            tasks.append((f"GLOBAL:{label}",key,tf,_ranges(first,last,lookback,unit,interval)))

    for key in sorted(participation_keys):
        for tf,unit,interval,lookback in [("1h","hours",1,45),("1d","days",1,180)]:
            tasks.append(("PARTICIPATION",key,tf,_ranges(first,last,lookback,unit,interval)))

    out=Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    manifest_rows=[]
    for index,(category,key,tf,chunks) in enumerate(tasks, start=1):
        try:
            series=_fetch_series(client,key,tf,chunks)
        except Exception as error:
            diagnostic={
                "schema":"bt100-core-history-failure-v1",
                "task_index":index,
                "category":category,
                "instrument_key":key,
                "timeframe":tf,
                "chunk_count":len(chunks),
                "error_type":type(error).__name__,
                "error":str(error),
                "production_writes":0,
                "production_neuron_calls":0,
                "trading_enabled":False,
            }
            (out/"failure.json").write_text(json.dumps(diagnostic,sort_keys=True,indent=2)+"\\n",encoding="utf-8")
            raise
        filename=f"{index:03d}_{hashlib.sha256(key.encode()).hexdigest()[:12]}_{tf}.json"
        (out/filename).write_text(json.dumps(series,sort_keys=True,separators=(",",":"))+"\n",encoding="utf-8")
        manifest_rows.append({
            "category":category,
            "instrument_key":key,
            "timeframe":tf,
            "file":filename,
            "series_sha256":series["series_sha256"],
            "candle_count":len(series["candles"]),
            "chunk_count":len(chunks),
            "first_candle":series["candles"][0][0],
            "last_candle":series["candles"][-1][0],
        })

    manifest={
        "schema":"bt100-core-history-manifest-v1",
        "first_target_date":first.isoformat(),
        "last_outcome_date":last.isoformat(),
        "series_count":len(manifest_rows),
        "global_catalog_sha256":global_doc["sha256"],
        "participation_approval_ref":participation.approval_ref,
        "series":manifest_rows,
        "production_writes":0,
        "production_neuron_calls":0,
        "trading_enabled":False,
    }
    manifest["manifest_sha256"]=_sha(manifest)
    (out/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--frozen-sessions",default="bt100/config/frozen_sessions_v1.json")
    parser.add_argument("--output-dir",default="bt100_artifacts/core_history")
    args=parser.parse_args()
    token=os.environ.get("UPSTOX_ANALYTICS_TOKEN","")
    if not token:
        raise SystemExit("UPSTOX_ANALYTICS_TOKEN missing")
    manifest=run(token,args.frozen_sessions,args.output_dir)
    print(json.dumps(manifest,sort_keys=True,indent=2))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
