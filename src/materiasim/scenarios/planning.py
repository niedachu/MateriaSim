"""Concrete scenario build plans; no independent execution or hidden protocol changes."""

from copy import deepcopy

from materiasim.builders.registry import get_builder


def build_plan(spec):
    """Return the implemented one-pipeline recipe with explicit inputs and real output obligations."""
    builder = spec["scenario"]["builder"]
    get_builder(builder["id"])
    return dict(contract_version=1, scenario=spec["scenario"]["kind"],
                steps=[dict(id="construct_system", builder=builder["id"], config=deepcopy(builder["config"]),
                            inputs=["models", "interaction_bundle", "boundary", "initial_protocol_stage"],
                            outputs=["coordinates", "topology", "mapping", "resolved_system", "initial_preparation"])])
