import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from settings import resolve_settings


class ResolveSettingsTests(unittest.TestCase):
    def test_defaults_survive_when_no_layer_overrides(self) -> None:
        resolved = resolve_settings({"retries": 3}, {}, {})
        self.assertEqual(resolved["retries"], 3)

    def test_environment_wins_over_defaults(self) -> None:
        resolved = resolve_settings({"endpoint": "default"}, {}, {"endpoint": "env"})
        self.assertEqual(resolved["endpoint"], "env")

    def test_environment_wins_over_file(self) -> None:
        resolved = resolve_settings(
            {"endpoint": "default"},
            {"endpoint": "file"},
            {"endpoint": "env"},
        )
        self.assertEqual(resolved["endpoint"], "env")

    def test_file_wins_over_defaults(self) -> None:
        resolved = resolve_settings({"timeout": 10}, {"timeout": 20}, {})
        self.assertEqual(resolved["timeout"], 20)

    def test_layers_are_not_mutated(self) -> None:
        defaults = {"retries": 3}
        file_values = {"retries": 4}
        env_values = {"retries": 5}
        resolve_settings(defaults, file_values, env_values)
        self.assertEqual(defaults, {"retries": 3})
        self.assertEqual(file_values, {"retries": 4})
        self.assertEqual(env_values, {"retries": 5})

    def test_unique_keys_from_every_layer_are_present(self) -> None:
        resolved = resolve_settings({"a": 1}, {"b": 2}, {"c": 3})
        self.assertEqual(resolved, {"a": 1, "b": 2, "c": 3})


if __name__ == "__main__":
    unittest.main()
