import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from duration import round_to_minutes


class RoundToMinutesTests(unittest.TestCase):
    def test_exact_half_minute_rounds_away_from_zero(self) -> None:
        self.assertEqual(round_to_minutes(30), 1)
        self.assertEqual(round_to_minutes(-30), -1)

    def test_just_below_half_minute_rounds_toward_zero(self) -> None:
        self.assertEqual(round_to_minutes(29), 0)
        self.assertEqual(round_to_minutes(-29), 0)

    def test_one_and_a_half_minutes_rounds_away_from_zero(self) -> None:
        self.assertEqual(round_to_minutes(90), 2)
        self.assertEqual(round_to_minutes(-90), -2)

    def test_result_is_an_integer(self) -> None:
        self.assertIsInstance(round_to_minutes(45), int)
        self.assertNotIsInstance(round_to_minutes(45), bool)

    def test_two_and_a_half_minutes_rounds_away_from_zero(self) -> None:
        self.assertEqual(round_to_minutes(150), 3)
        self.assertEqual(round_to_minutes(-150), -3)

    def test_whole_minutes_are_unchanged(self) -> None:
        self.assertEqual(round_to_minutes(0), 0)
        self.assertEqual(round_to_minutes(60), 1)
        self.assertEqual(round_to_minutes(-120), -2)


if __name__ == "__main__":
    unittest.main()
