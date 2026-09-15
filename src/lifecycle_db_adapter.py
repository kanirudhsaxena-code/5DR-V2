"""Production database adapter contract for 5DR V2.2.2 lifecycle accounting.

Uses a caller-supplied DB-API connection factory. No credentials are stored here.
The adapter is deliberately narrow: canonical reads plus parameterized execution of
SQL already produced by the approved lifecycle executor.
"""
from __future__ import annotations

from contextlib import closing
from typing import Callable, Iterable


class LifecycleDbAdapter:
    def __init__(self, connect: Callable[[], object]):
        self._connect = connect

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        with closing(self._connect()) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                columns = [d[0] for d in cur.description]
                return [dict(zip(columns, row)) for row in cur.fetchall()]

    def actionable_recommendations(self) -> list[dict]:
        return self._fetchall(
            """SELECT * FROM v_recommendation_lifecycle_v222
               WHERE lifecycle_status IN ('OPEN','OPEN_T1_HIT')
                 AND recommendation IN ('BUY_CE','BUY_PE','BUY_CONVEXITY')
               ORDER BY issuance_timestamp"""
        )

    def existing_event_types(self, forecast_id: str) -> set[str]:
        rows = self._fetchall(
            "SELECT event_type FROM recommendation_events WHERE forecast_id = %s",
            (forecast_id,),
        )
        return {r['event_type'] for r in rows}

    def due_checkpoints(self) -> list[dict]:
        return self._fetchall(
            """SELECT * FROM outcome_checkpoints
               WHERE status = 'DUE' AND due_date <= CURRENT_DATE
               ORDER BY due_date, checkpoint_id"""
        )

    def execute_lifecycle_sql(self, sql: str, params: dict, *, writes_enabled: bool = False) -> int:
        if not writes_enabled:
            return 0
        normalized = sql.lstrip().upper()
        allowed = normalized.startswith('INSERT INTO RECOMMENDATION_EVENTS') or normalized.startswith('UPDATE OUTCOME_CHECKPOINTS')
        if not allowed:
            raise ValueError('lifecycle adapter rejected non-allowlisted SQL')
        with closing(self._connect()) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    count = max(cur.rowcount, 0)
                conn.commit()
                return count
            except Exception:
                conn.rollback()
                raise
