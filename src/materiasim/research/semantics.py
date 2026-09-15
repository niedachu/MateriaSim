"""Explicit repeat slots and method-aware declarations for research v2."""

from materiasim.analysis.registry import get_analyzer
from materiasim.scenarios.registry import get_scenario
from materiasim.specs.schema import fields, identifier, integer, number


def seed_values(spec):
    """Read actual scenario and velocity-generation slots, never inventing a prebuilt packing seed."""
    config = spec["scenario"]["builder"]["config"]
    values = {slot: config[key] for slot, key in get_scenario(spec["scenario"]["kind"]).seed_fields}
    values.update({"velocity_" + s["id"]: s["seed"] for s in spec["protocol"]["stages"]
                   if s["velocities"] == "generate"})
    return values


def apply_repeat(spec, repeat):
    """Validate exact required slots and assign only explicitly declared repeat seeds in-place."""
    fields(repeat, ("id", "seeds"), "repeat")
    identifier(repeat["id"], "repeat.id")
    fields(repeat["seeds"], seed_values(spec), "repeat.seeds")
    for seed in repeat["seeds"].values():
        integer(seed, 1, 2147483646, "repeat seed")
    for slot, key in get_scenario(spec["scenario"]["kind"]).seed_fields:
        spec["scenario"]["builder"]["config"][key] = repeat["seeds"][slot]
    for stage in spec["protocol"]["stages"]:
        if stage["velocities"] == "generate":
            stage["seed"] = repeat["seeds"]["velocity_" + stage["id"]]


def observables_check(values):
    """Require unique request/method/metric/unit declarations owned by real registered methods."""
    if not isinstance(values, list):
        raise ValueError("observables must be an explicit list, possibly empty")
    seen = set()
    for item in values:
        fields(item, ("request_id", "method", "metric", "unit"), "observable")
        identifier(item["request_id"], "observable.request_id")
        method = get_analyzer(item["method"])
        if (item["metric"], item["unit"]) not in method.metrics:
            raise ValueError("Metric/unit is not provided by the selected analysis method")
        key = (item["request_id"], item["metric"])
        if key in seen:
            raise ValueError("Duplicate observable")
        seen.add(key)


def match_observables(spec, observables):
    """Require exact coverage of configured requests; undeclared or missing analyses cannot disappear."""
    expected = {item["id"]: item["kind"] for item in spec["analysis_requests"]}
    actual = {}
    for item in observables:
        if item["request_id"] in actual and actual[item["request_id"]] != item["method"]:
            raise ValueError("Observable request has conflicting methods")
        actual[item["request_id"]] = item["method"]
    if actual != expected:
        raise ValueError("Declared observables must cover the exact configured analysis requests")


def rules_check(rules, observables):
    """Check bounded engineering rules without interpreting arbitrary code or scientific approval."""
    fields(rules, ("description", "checks"), "decision_rules")
    if not isinstance(rules["description"], str) or not rules["description"].strip():
        raise ValueError("decision_rules.description requires text")
    if not isinstance(rules["checks"], list) or not 1 <= len(rules["checks"]) <= 32:
        raise ValueError("Explicit bounded engineering checks required")
    seen = set()
    for rule in rules["checks"]:
        if not isinstance(rule, dict):
            raise ValueError("Rule must be an object")
        kind = rule.get("kind")
        keys = ("id", "kind")
        if kind == "metric_range":
            keys += ("request_id", "metric", "unit", "minimum", "maximum")
        elif kind not in ("all_tasks_completed", "analysis_valid"):
            raise ValueError("Unknown engineering rule; scientific approval cannot be inferred")
        fields(rule, keys, "rule")
        identifier(rule["id"], "rule.id")
        if rule["id"] in seen:
            raise ValueError("Duplicate rule id")
        seen.add(rule["id"])
        if kind == "metric_range":
            if not any(all(rule[key] == item[key] for key in ("request_id", "metric", "unit")) for item in observables):
                raise ValueError("Range rule requires a declared metric and matching unit")
            number(rule["minimum"], -1e15, 1e15, "minimum")
            number(rule["maximum"], rule["minimum"], 1e15, "maximum")


def evaluate_rules(rules, rows):
    """Return pass/fail/not_assessed with task evidence; no rule grants scientific validation."""
    results = []
    for rule in rules["checks"]:
        evidence = [dict(task_id=row["task_id"], status=row["status"]) for row in rows]
        outcome = "pass" if all(row["status"] == "completed" for row in rows) else "fail"
        if rule["kind"] == "metric_range":
            values = [dict(task_id=row["task_id"], value=o["value"], report_sha256=o["report_sha256"])
                      for row in rows for o in row["observations"]
                      if (o["request_id"], o["metric"], o["unit"]) ==
                      (rule["request_id"], rule["metric"], rule["unit"])]
            evidence = values
            outcome = ("not_assessed" if len(values) != len(rows) else
                       "pass" if all(rule["minimum"] <= v["value"] <= rule["maximum"] for v in values) else "fail")
        results.append(dict(id=rule["id"], kind=rule["kind"], status=outcome, evidence=evidence))
    return dict(scope="engineering", checks=results, scientific_quality="not_assessed")
