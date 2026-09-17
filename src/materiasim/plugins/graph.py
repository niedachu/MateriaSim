"""Deterministic dependency validation for explicitly registered capabilities, not code loading."""

from materiasim.errors import MateriaSimError


def order(entries, selected, check_conflicts=True):
    """Return dependency-first IDs; reject absent/disabled dependencies, cycles and task conflicts."""
    selected = set(selected)
    visiting, finished, result = set(), set(), []

    def visit(key):
        """Visit one registered dependency; traversal has no import or installation side effects."""
        if key not in entries or key not in selected:
            raise MateriaSimError("MISSING_CAPABILITY", f"Missing/disabled capability: {key}", category="capability")
        if key in visiting:
            raise MateriaSimError("PLUGIN_DEPENDENCY_CYCLE", f"Capability cycle at {key}", category="capability")
        if key in finished:
            return
        item = entries[key]
        if item["id"] != key or item["contract_version"] != 1:
            raise MateriaSimError("PLUGIN_CONTRACT_MISMATCH", f"Invalid descriptor: {key}", category="capability")
        if check_conflicts and selected.intersection(item["conflicts"]):
            raise MateriaSimError("PLUGIN_CONFLICT", f"Conflicting task capability: {key}", category="capability")
        visiting.add(key)
        for dependency in sorted(item["requires"]):
            visit(dependency)
        visiting.remove(key)
        finished.add(key)
        result.append(key)

    for key in sorted(selected):
        visit(key)
    return result
