"""Known-answer periodic water-contact counting tests using the analysis environment."""

import unittest

import numpy as np

from materials_sim.hydration import contact_sets


class ContactTests(unittest.TestCase):
    """Check periodic wrapping and unique-water counting independently of a trajectory."""

    def test_periodic_contact(self):
        """A water across the periodic edge is within a 0.1 nm site cutoff."""
        waters = np.array([[9.8, 0, 0], [5, 0, 0]], dtype=np.float32)
        sites = np.array([[.2, 0, 0]], dtype=np.float32)
        actual = contact_sets(waters, sites, np.array([10, 10, 10, 90, 90, 90]), .1)
        self.assertEqual(actual, {0})

    def test_water_union_deduplicates(self):
        """A water contacted by two site atoms contributes only once to their union."""
        waters = np.array([[2, 0, 0], [7, 0, 0]], dtype=np.float32)
        box = np.array([10, 10, 10, 90, 90, 90])
        first = contact_sets(waters, np.array([[1.8, 0, 0]]), box, .1)
        second = contact_sets(waters, np.array([[2.2, 0, 0]]), box, .1)
        self.assertEqual(len(first | second), 1)


if __name__ == "__main__":
    unittest.main()
