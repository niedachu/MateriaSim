from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.hydration_core import (
    minimum_image_delta,
    select_water_ids_reference,
    summarize_counts,
    union_unique_water_ids,
)


class HydrationCoreTests(unittest.TestCase):
    def test_union_deduplicates_waters_across_sites(self) -> None:
        hits = {
            "sulfonate": {1, 2, 3, 4, 5, 6},
            "ether": {5, 6, 7, 8},
            "imidazolium": {8, 9, 10},
        }
        self.assertEqual(union_unique_water_ids(hits), set(range(1, 11)))

    def test_minimum_image_wraps_across_box_boundary(self) -> None:
        self.assertAlmostEqual(minimum_image_delta(4.3, 4.5), -0.2)
        self.assertAlmostEqual(minimum_image_delta(-4.3, 4.5), 0.2)

    def test_reference_selection_uses_site_cutoffs_and_pbc(self) -> None:
        sites = {
            "sulfonate": [(0.10, 0.10, 0.10)],
            "ether": [(2.00, 2.00, 2.00)],
            "imidazolium": [(1.00, 1.00, 1.00)],
        }
        cutoffs = {"sulfonate": 0.30, "ether": 0.25, "imidazolium": 0.30}
        waters = {
            1: (4.40, 0.10, 0.10),
            2: (2.20, 2.00, 2.00),
            3: (1.20, 1.00, 1.00),
            4: (1.15, 1.00, 1.00),
            5: (3.00, 3.00, 3.00),
        }
        selected = select_water_ids_reference(sites, cutoffs, waters, (4.5, 4.5, 4.5))
        self.assertEqual(selected["sulfonate"], {1})
        self.assertEqual(selected["ether"], {2})
        self.assertEqual(selected["imidazolium"], {3, 4})
        self.assertEqual(union_unique_water_ids(selected), {1, 2, 3, 4})

    def test_summary_has_expected_statistics(self) -> None:
        summary = summarize_counts([8, 9, 10, 11, 12])
        self.assertEqual(summary["mean"], 10.0)
        self.assertEqual(summary["median"], 10.0)
        self.assertEqual(summary["minimum"], 8)
        self.assertEqual(summary["maximum"], 12)

    def test_invalid_cutoff_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            select_water_ids_reference(
                {"site": [(0.0, 0.0, 0.0)]},
                {"site": 0.0},
                {1: (0.0, 0.0, 0.0)},
                (4.5, 4.5, 4.5),
            )


if __name__ == "__main__":
    unittest.main()
