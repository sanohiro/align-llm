import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from decode import decode_record
from encode import encode_record


class RecordCodecTests(unittest.TestCase):
    def assert_round_trip(self, fields) -> None:
        encoded = encode_record(fields)
        self.assertNotIn("\n", encoded)
        self.assertEqual(decode_record(encoded), fields)

    def test_backslash_inside_field_round_trips(self) -> None:
        self.assert_round_trip(["a\\b", "c"])

    def test_delimiter_inside_field_round_trips(self) -> None:
        self.assert_round_trip(["a|b", "c"])

    def test_empty_fields_round_trip(self) -> None:
        self.assert_round_trip(["", "", ""])

    def test_escaped_delimiter_pair_round_trips(self) -> None:
        self.assert_round_trip(["a\\|b", "c"])

    def test_newline_inside_field_round_trips(self) -> None:
        self.assert_round_trip(["first\nsecond", "third"])

    def test_plain_fields_round_trip(self) -> None:
        self.assert_round_trip(["alpha", "beta", "gamma"])

    def test_single_field_round_trips(self) -> None:
        self.assert_round_trip(["only"])


if __name__ == "__main__":
    unittest.main()
