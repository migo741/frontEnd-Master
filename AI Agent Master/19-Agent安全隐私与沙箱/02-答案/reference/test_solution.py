from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from solution import SecurityViolation, run_demo_code, safe_workspace_path, validate_archive, validate_url


class SecurityTest(unittest.TestCase):
    def test_ssrf_rejects_loopback_and_cloud_metadata(self) -> None:
        for ip in ("127.0.0.1", "169.254.169.254", "10.0.0.1", "::1"):
            with self.assertRaises(SecurityViolation):
                validate_url("https://example.com/data", [ip])

    def test_url_rejects_credentials_and_odd_ports(self) -> None:
        with self.assertRaises(SecurityViolation):
            validate_url("https://user:pass@example.com", ["93.184.216.34"])
        with self.assertRaises(SecurityViolation):
            validate_url("https://example.com:8080", ["93.184.216.34"])

    def test_workspace_path_blocks_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(safe_workspace_path(root, "src/app.py"), (root / "src/app.py").resolve())
            with self.assertRaises(SecurityViolation):
                safe_workspace_path(root, "../../.env")

    def test_archive_budget_blocks_zip_bomb_and_traversal(self) -> None:
        with self.assertRaises(SecurityViolation):
            validate_archive([("../../escape", 1, 1)])
        with self.assertRaises(SecurityViolation):
            validate_archive([("large.bin", 1_000_000, 1)])

    def test_demo_runner_executes_small_pure_code(self) -> None:
        self.assertEqual(run_demo_code("print(sum(range(5)))").strip(), "10")

    def test_demo_runner_rejects_import_and_caps_output(self) -> None:
        with self.assertRaises(SecurityViolation):
            run_demo_code("import os; print(os.environ)")
        with self.assertRaisesRegex(SecurityViolation, "output"):
            run_demo_code("print('x' * 1000)", max_output=20)


if __name__ == "__main__":
    unittest.main(verbosity=2)
