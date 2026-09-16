"""Current entry-point links must resolve after the package/document migration."""

import re
import json
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def unique_object(pairs):
    """Build a JSON metadata object, rejecting duplicate keys instead of hiding prior values."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate metadata key: {key}")
        result[key] = value
    return result


def reject_constant(value):
    """Reject nonstandard JSON constants in metadata; return no substitute value."""
    raise ValueError(f"Nonstandard JSON constant: {value}")


def metadata(text):
    """Read the governed JSON frontmatter subset; reject missing delimiters or non-object data."""
    match = re.match(r"^---\n(.*?)\n---(?:\n|$)", text, re.S)
    if not match:
        raise ValueError("Missing metadata delimiters")
    result = json.loads(match.group(1), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(result, dict):
        raise ValueError("Metadata must be an object")
    return result


def governed_documents():
    """Return actual plan and knowledge records, excluding navigation, references and templates."""
    plans = sorted((ROOT / "docs/plans").rglob("*__*.md"))
    knowledge = [path for path in (ROOT / "docs/knowledge").rglob("*.md")
                 if path.parts[-2] not in ("templates", "references") and path.name not in ("README.md", "INDEX.md")]
    return plans, sorted(knowledge)


class DocumentationTests(unittest.TestCase):
    """Check maintained guides and skill routing, not historical absolute runtime locations."""

    def test_current_relative_links_resolve(self):
        """Local Markdown links in current documentation and touched plans point to real targets."""
        paths = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "src/materiasim/AGENTS.md",
                 ROOT / "materials_simulation/README.md", ROOT / "materials_simulation/AGENTS.md"]
        for name in ("2026-09-14__execution__cpu-gpu-runtime__implementation-plan.md",
                     "2026-09-14__multicomponent-multiscenario__implementation-plan.md",
                     "2026-09-15__architecture__simulation-package-and-research-bundles__implementation-plan.md"):
            paths.append(ROOT / "docs/plans" / name)
        for folder in ("docs/guides", "skills", "studies", "docs/validation", "docs/knowledge", "docs/plans"):
            paths.extend((ROOT / folder).rglob("*.md"))
        for path in paths:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
                target = target.strip("<>").split("#", 1)[0]
                if not target or target.startswith(("http:", "https:", "/")):
                    continue
                with self.subTest(document=path.relative_to(ROOT), target=target):
                    self.assertTrue((path.parent / target).exists())

    def test_skill_identity_and_authorization_preserved(self):
        """Narrow skill edits preserve names/descriptions and do not introduce new executable hooks."""
        for name in ("simulation-research", "simulation-diagnostics"):
            path = ROOT / "skills" / name / "SKILL.md"
            text = path.read_text()
            self.assertTrue(text.startswith("---\nname: " + name + "\ndescription: "))
            self.assertEqual(len(text.split("---", 2)), 3)
            self.assertIn("../../src/materiasim/AGENTS.md", text)

    def test_governed_metadata_is_complete_and_unique(self):
        """Validate types, states, stable identities and dates of every governed document."""
        plans, knowledge = governed_documents()
        self.assertTrue(plans)
        self.assertTrue(knowledge)
        seen = set()
        common = {"type", "status", "owner", "created", "last_updated", "canonical", "doc_id",
                  "scope", "supersedes", "superseded_by", "related_code", "rag_exclude"}
        kinds = {prefix + "-plan" for prefix in ("architecture", "implementation", "migration", "refactor",
                 "cleanup", "research", "validation", "governance")} | {"execution-guide"}
        for path in plans + knowledge:
            with self.subTest(document=path.relative_to(ROOT)):
                record = metadata(path.read_text())
                self.assertTrue(common <= record.keys())
                self.assertNotIn(record["doc_id"], seen)
                seen.add(record["doc_id"])
                self.assertTrue(record["scope"].strip())
                self.assertIs(type(record["canonical"]), bool)
                self.assertIs(type(record["rag_exclude"]), bool)
                self.assertLessEqual(date.fromisoformat(record["created"]), date.fromisoformat(record["last_updated"]))
                if path in plans:
                    self.assertEqual(record["type"], "work_plan")
                    self.assertTrue({"plan_kind", "module", "domain", "source_path", "related_kb",
                                     "implementation_status"} <= record.keys())
                    self.assertIn(record["status"], {"draft", "active", "blocked", "completed", "superseded", "rejected", "archived"})
                    self.assertIn(record["plan_kind"], kinds)
                    self.assertTrue(record["rag_exclude"])
                else:
                    self.assertEqual(record["type"], "knowledge")
                    self.assertTrue({"doc_kind", "title", "source_refs", "related_assets", "related_plans",
                                     "review", "limitations"} <= record.keys())
                    self.assertIn(record["status"], {"draft", "current", "deprecated", "superseded", "archived"})
                    self.assertEqual(set(record["review"]), {"theory", "implementation", "evidence", "applicability"})
                    self.assertTrue(record["limitations"])
                    if record["status"] != "current":
                        self.assertTrue(record["rag_exclude"])

    def test_relations_sources_and_indexes_resolve(self):
        """Require knowledge/plan IDs, assets, provenance sources and navigation to resolve locally."""
        plans, knowledge = governed_documents()
        records = {metadata(path.read_text())["doc_id"]: metadata(path.read_text()) for path in plans + knowledge}
        sources = json.loads((ROOT / "docs/knowledge/references/sources.json").read_text(), object_pairs_hook=unique_object)
        source_ids = {source["id"] for source in sources["sources"]}
        self.assertEqual(len(source_ids), len(sources["sources"]))
        for source in sources["sources"]:
            self.assertTrue({"id", "title", "authors", "url", "version", "accessed", "locator",
                             "read_scope", "limitations", "access"} <= source.keys())
            self.assertTrue(source["url"].startswith("https://"))
            date.fromisoformat(source["accessed"])
        for path in plans + knowledge:
            record = metadata(path.read_text())
            with self.subTest(document=path.relative_to(ROOT)):
                for field in ("related_kb", "related_plans", "supersedes", "superseded_by"):
                    self.assertIsInstance(record.get(field, []), list)
                    for target in record.get(field, []):
                        self.assertIn(target, records)
                        if field in ("supersedes", "superseded_by"):
                            reverse = "superseded_by" if field == "supersedes" else "supersedes"
                            self.assertIn(record["doc_id"], records[target][reverse])
                for field in ("related_code", "related_assets"):
                    self.assertIsInstance(record.get(field, []), list)
                    for target in record.get(field, []):
                        self.assertFalse(Path(target).is_absolute())
                        self.assertTrue((ROOT / target).exists(), target)
                        self.assertTrue((ROOT / target).resolve().is_relative_to(ROOT))
                self.assertTrue(set(record.get("source_refs", [])) <= source_ids)
                if path in knowledge and record["review"]["theory"] == "source_checked":
                    self.assertTrue(record["source_refs"])
                index = ROOT / ("docs/plans/INDEX.md" if path in plans else "docs/knowledge/INDEX.md")
                self.assertIn(path.relative_to(index.parent).as_posix(), index.read_text())
                if path in plans:
                    self.assertIn(record["doc_id"], (ROOT / "docs/plans/MIGRATION_MAP.md").read_text())

    def test_invalid_metadata_is_not_silently_accepted(self):
        """Exercise duplicate keys, malformed/missing metadata and nonstandard constants as failures."""
        invalid = ['---\n{"status":"draft","status":"current"}\n---\n',
                   '---\n{"value":NaN}\n---\n', '---\n[]\n---\n',
                   '---\n{"status":}\n---\n', '# no metadata']
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                metadata(text)
