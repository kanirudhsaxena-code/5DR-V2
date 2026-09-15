"""Reusable live acquisition function for the isolated Upstox experiment.

Read-only only. No database, lifecycle, forecast or trading writes.
"""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from experiments.upstox_reliability import annotate_sample
from experiments.upstox_sanitizer import sanitize_live_envelopes
from experiments.upstox_session import get_nfo_market_status, select_session_valid_expiry
from experiments.upstox_transport import CurlOpener
from phase1.upstox import NIFTY, PipelineError, ReadOnlyClient

IST = ZoneInfo("Asia/Kolkata")
EXPECTED_ERRORS = (PipelineError, ValueError, KeyError, TypeError, StopIteration)


class AcquisitionStageError(Exception):
    """Carries only a fixed stage plus the original error object for safe mapping."""
    def __init__(self, stage, error):
        super().__init__(stage)
        self.stage = stage
        self.error = error


def github_audit_context():
    return {
        "github_run_id": os.getenv("GITHUB_RUN_ID"),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.getenv("GITHUB_SHA"),
        "github_event_name": os.getenv("GITHUB_EVENT_NAME"),
    }


def acquire_live_sample(token, audit_context=None):
    stage = "INIT"
    try:
        client = ReadOnlyClient(token, opener=CurlOpener())
        stage = "OPTION_CONTRACTS"
        contracts = client.contracts()
        expiries = sorted({
            row["expiry"]
            for row in contracts["payload"]["data"]
            if row.get("underlying_key") == NIFTY
        })
        today = datetime.now(IST).date()

        stage = "MARKET_STATUS"
        market_session = get_nfo_market_status(token)
        expiry = select_session_valid_expiry(expiries, today, market_session["status"])

        stage = "INTRADAY_CANDLES"
        intraday = client.intraday()
        stage = "OPTION_CHAIN"
        chain = client.chain(expiry)

        stage = "SANITIZE"
        result = sanitize_live_envelopes(
            contracts,
            intraday,
            chain,
            today,
            selected_expiry=expiry,
        )
        result["market_session"] = {
            "exchange": market_session["exchange"],
            "status": market_session["status"],
            "last_updated": market_session["last_updated"],
        }
        result["provenance"]["market_status"] = {
            "source_path": market_session["source_path"],
            "sha256": market_session["sha256"],
            "received_at": market_session["received_at"],
        }
        result["transport"] = "curl"

        stage = "RELIABILITY"
        annotate_sample(
            result,
            now=datetime.now(timezone.utc),
            audit_context=audit_context or github_audit_context(),
        )
        result["status"] = "LIVE_SAMPLE_PASSED"
        return result
    except AcquisitionStageError:
        raise
    except EXPECTED_ERRORS as error:
        raise AcquisitionStageError(stage, error) from None
