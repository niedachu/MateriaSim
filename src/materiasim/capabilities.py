"""Expose the same implemented components used by validation and actual workflows."""

from materiasim.analysis.registry import ANALYZERS
from materiasim.engines.registry import ENGINES
from materiasim.scenarios.registry import SCENARIOS


def capabilities():
    """Return static component contracts without probing tools or claiming environmental/scientific success."""
    from materiasim.plugins.builtin import catalog
    return dict(contract_version=1,
                campaign=dict(contract_version=3, modes=["local_rules", "local_agent_decisions"], device="cpu",
                              purpose="engineering_smoke", capabilities=list(catalog()),
                              external_agent=False, local_agent_protocol=True, dynamic_plugins=False, active_relocation=False),
                engines=[dict(id=item.id, purposes=list(item.purposes), implementation="implemented")
                         for item in ENGINES.values()],
                scenarios=[dict(id=item.id, engines=list(item.engines), dependencies=list(item.dependencies),
                                implementation="implemented") for item in SCENARIOS.values()],
                analysis=[dict(id=item.id, inputs=[dict(role=role, format=kind) for role, kind in item.inputs],
                               implementation="implemented") for item in ANALYZERS.values()],
                experiment_schemas=[1, 2, 3], executable_schemas=[2, 3], run_schema=3,
                research_schemas=[1, 2], frozen_plan_schema=3, execution_profiles=[1, 2, 3],
                purpose_policy=dict(contract_version=1, trust="local review attestation; not authenticated scientific approval"),
                storage=dict(checked_copies=True, independent_generations=True, archive="read_only", active_relocation=False),
                gpu=dict(implementation="candidate", backend="CUDA", ranks=1, devices=1,
                         offload=["nonbonded", "pme"], engineering_evidence="not_assessed"),
                compatibility="requires_validated_input", environment="not_checked",
                scientific_quality="not_assessed",
                engineering_evidence=dict(scope="previous macOS CPU subset; not this source revision",
                    reference="docs/validation/2026-09-15__architecture-bcd-acceptance.md"),
                not_implemented=["mixed_solvents", "concentration_recipes", "polymers", "solids", "interfaces",
                                 "lammps", "gpu_bonded_update", "remote_execution", "authenticated_approval"])
