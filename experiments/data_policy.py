"""Cost-aware request policy over the provider-neutral requirements registry."""
from copy import deepcopy

from experiments.data_contract import DataArchitectureError
from experiments.data_requirements import CONSUMERS, requirements

NON_PROVIDER_AVAILABILITY = {"UNAVAILABLE", "EXTERNAL_ONLY"}


def build_request_plan(consumer, *, experiment_only=True, include_provisioned=False,
                       variable_ids=None):
    if consumer not in CONSUMERS:
        raise DataArchitectureError("unknown consumer")
    wanted = set(variable_ids or [])
    rows = requirements(consumer)
    plan = []
    for row in rows:
        if wanted and row["variable_id"] not in wanted:
            continue
        if experiment_only and not row["enabled_experiment"]:
            if not include_provisioned:
                continue
        if row["upstox_availability"] in NON_PROVIDER_AVAILABILITY and not include_provisioned:
            continue
        plan.append(deepcopy(row))
    if wanted:
        found = {row["variable_id"] for row in plan}
        unresolved = wanted - found
        if unresolved:
            raise DataArchitectureError("requested variable unavailable under current policy")
    return plan


def enabled_variable_ids(consumer):
    return tuple(row["variable_id"] for row in build_request_plan(consumer))


def validate_cost_posture():
    """Hard policy invariants preventing accidental warehouse-scale collection."""
    five_dr = build_request_plan("5DR")
    if not five_dr:
        raise DataArchitectureError("5DR experimental plan empty")
    if build_request_plan("EDGE_STOCK") or build_request_plan("EDGE_IPO"):
        raise DataArchitectureError("EDGE background collection must remain disabled")
    prohibited = {"TICK_ARCHIVE", "FULL_DEPTH_30", "ALL_NSE_STOCKS", "ALL_OPTION_CHAINS"}
    all_ids = {row["variable_id"] for row in requirements()}
    if prohibited & all_ids:
        raise DataArchitectureError("unbounded data collection provision enabled")
    return True
