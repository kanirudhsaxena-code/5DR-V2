"""5DR V2.2.2 autonomous lifecycle orchestration.

Pure orchestration: validated evidence in, proposed append-only actions out.
Production execution/scheduling remains a separate approval-gated layer.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from src.lifecycle_evidence import OptionEvidence, path_can_close
from src.lifecycle_worker import derive_events, checkpoint_due, should_process

@dataclass(frozen=True)
class ProposedAction:
    kind: str
    payload: dict


def plan_recommendation(recommendation: dict, lifecycle_status: str,
                        evidence: OptionEvidence | None, existing_types: set[str]) -> list[ProposedAction]:
    if not should_process(recommendation['action'], lifecycle_status):
        return []
    if evidence is None:
        return [ProposedAction('NO_WRITE', {'reason':'NO_VERIFIED_EVIDENCE'})]
    evidence.validate_for(instrument=recommendation['instrument'], strike=recommendation['strike'], expiry=recommendation['expiry'])
    events = derive_events(recommendation['entry'], recommendation['stop'], recommendation['target1'], recommendation['target2'], evidence.premium, existing_types)
    terminal = {'T2_HIT','SL_HIT','THESIS_EXIT','TIME_EXIT'}
    if any(e['event_type'] in terminal for e in events) and not path_can_close(evidence):
        return [ProposedAction('MARK', {'premium': evidence.premium, 'source_ref': evidence.source_ref,
                                        'observed_at': evidence.observed_at,
                                        'note':'Terminal threshold visible but ordering not proven; fail closed.'})]
    return [ProposedAction('EVENT', {**e, 'source_ref': evidence.source_ref,
                                     'observed_at': evidence.observed_at}) for e in events] or [
           ProposedAction('MARK', {'premium': evidence.premium, 'source_ref': evidence.source_ref,
                                   'observed_at': evidence.observed_at})]


def plan_due_checkpoints(checkpoints: list[dict], as_of: date, market_evidence: dict | None) -> list[ProposedAction]:
    actions=[]
    for cp in checkpoints:
        if not checkpoint_due(cp['due_date'], as_of, cp['status']):
            continue
        if not market_evidence or not market_evidence.get('verified'):
            actions.append(ProposedAction('NO_WRITE', {'checkpoint_id':cp['checkpoint_id'], 'reason':'CHECKPOINT_EVIDENCE_UNVERIFIED'}))
            continue
        actions.append(ProposedAction('CHECKPOINT', {'checkpoint_id':cp['checkpoint_id'], **market_evidence}))
    return actions


def efficacy_ready(lifecycle_status: str, primary_outcome: str | None, checkpoint_count: int) -> bool:
    return lifecycle_status.startswith('CLOSED_') and primary_outcome in {'WIN','LOSS'} and checkpoint_count > 0
