import importlib.util
import unittest
from pathlib import Path


def _import_policy():
    policy_path = Path(__file__).resolve().parents[1] / "app" / "core" / "policy.py"
    spec = importlib.util.spec_from_file_location("core_policy", policy_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


core_policy = _import_policy()
check_extension_limits = core_policy.check_extension_limits
run_policy_checks = core_policy.run_policy_checks


class PolicyExtensionTests(unittest.TestCase):
    def test_check_extension_limits_allows_simple_extension(self):
        extension = {"steps": ["a", "b", "c"]}
        self.assertIsNone(check_extension_limits(extension))

    def test_check_extension_limits_rejects_large_array(self):
        extension = {"steps": list(range(100))}
        message = check_extension_limits(extension)
        self.assertIsInstance(message, str)
        self.assertIn("배열 길이", message)

    def test_run_policy_checks_detects_deep_extension(self):
        extension = {}
        cursor = extension
        for _ in range(8):
            cursor["child"] = {}
            cursor = cursor["child"]

        card = {"name": "Recursive Agent", "url": "http://localhost", "extension": extension}
        result = run_policy_checks(card, agents=[])
        self.assertEqual(result.get("status"), "error")
        self.assertIn("extension", result.get("message", ""))


if __name__ == "__main__":
    unittest.main()
