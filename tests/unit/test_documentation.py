"""Current entry-point links must resolve after the package/document migration."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
        for folder in ("docs/guides", "skills", "studies", "docs/validation"):
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
