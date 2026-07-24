import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from inclusive_range import inclusive_total


class InclusiveTotalTests(unittest.TestCase):
    def test_positive_interval_includes_stop(self) -> None:
        self.assertEqual(inclusive_total(1, 5), 15)

    def test_single_value_interval(self) -> None:
        self.assertEqual(inclusive_total(4, 4), 4)

    def test_interval_crossing_zero(self) -> None:
        self.assertEqual(inclusive_total(-2, 2), 0)

    def test_descending_interval_is_empty(self) -> None:
        self.assertEqual(inclusive_total(3, 1), 0)


if __name__ == "__main__":
    unittest.main()
