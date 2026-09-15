"""Bounded linear stage identities and coordinate/velocity/checkpoint handoff."""

def validate_stages(stages):
    """Validate stage IDs, targets and inheritance without reading engine files; return None."""
    from materiasim.specs.schema import fields, identifier, integer, number

    if not isinstance(stages, list) or not 2 <= len(stages) <= 8:
        raise ValueError("Engineering protocol requires 2–8 explicit stages")
    seen, previous = set(), None
    for stage in stages:
        fields(stage, ("id", "type", "mdp", "steps", "input", "velocities", "seed",
                       "time_origin_ps", "step_origin"), "stage")
        identifier(stage["id"], "stage.id")
        identifier(stage["mdp"], "stage.mdp")
        if stage["id"] in seen:
            raise ValueError("Duplicate stage ID")
        seen.add(stage["id"])
        if stage["type"] not in ("minimization", "dynamics"):
            raise ValueError("Unsupported stage type")
        minimize = stage["type"] == "minimization"
        if minimize != (previous is None):
            raise ValueError("Current protocol starts with one minimization, followed by dynamics")
        integer(stage["steps"], 1, 5000 if minimize else 2000, "stage.steps")
        integer(stage["step_origin"], 0, 1000000, "step_origin")
        number(stage["time_origin_ps"], 0, 1000000, "time_origin_ps")
        fields(stage["input"], ("stage_id", "kind"), "stage.input")
        if stage["input"]["stage_id"] != (previous["id"] if previous else None):
            raise ValueError("Input must reference the immediately preceding stage, or initial build")
        expected_velocity = "none" if minimize else ("generate" if previous["type"] == "minimization" else "inherit")
        expected_input = "checkpoint" if expected_velocity == "inherit" else "coordinates"
        if stage["velocities"] != expected_velocity or stage["input"]["kind"] != expected_input:
            raise ValueError("Invalid coordinate/velocity/checkpoint inheritance")
        if expected_velocity == "generate":
            integer(stage["seed"], 1, 2147483646, "velocity seed")
        elif stage["seed"] is not None:
            raise ValueError("Only velocity generation accepts a seed")
        if minimize and (stage["time_origin_ps"] != 0 or stage["step_origin"] != 0):
            raise ValueError("Minimization does not have a dynamics time origin")
        previous = stage
