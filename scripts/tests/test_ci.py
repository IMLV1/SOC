import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci_gate.py"
spec = importlib.util.spec_from_file_location("ci_gate", SCRIPT)
assert spec and spec.loader
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class GateTests(unittest.TestCase):
    def test_only_all_success_passes(self):
        for result in ["failure", "cancelled", "skipped", None, "", "success"]:
            with self.subTest(result=result):
                self.assertEqual(
                    gate.passes(
                        {"a": {"result": "success"}, "b": {"result": result}},
                        ["a", "b"],
                    ),
                    result == "success",
                )

    def test_missing_or_malformed_fails(self):
        for value in [
            None,
            [],
            {},
            {"a": {}},
            {"a": "success"},
            {"extra": {"result": "success"}},
        ]:
            with self.subTest(value=value):
                self.assertFalse(gate.passes(value, ["a"]))
        self.assertFalse(gate.passes({}, []))

    def test_cli_exit_codes(self):
        for data, expected in [
            ("broken", 1),
            ("{}", 1),
            (json.dumps({"a": {"result": "success"}}), 0),
        ]:
            with self.subTest(data=data):
                process = subprocess.run(
                    [sys.executable, str(SCRIPT), "a"],
                    env={**os.environ, "CI_NEEDS": data},
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(process.returncode, expected)

    def test_workflow_gate_covers_all_jobs_without_skips(self):
        # BaseLoader retains YAML's 'on' key (PyYAML's default YAML 1.1 treats it as boolean).
        workflow = yaml.load(
            (ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader
        )
        jobs = workflow["jobs"]
        final = jobs["ci-gate"]
        self.assertEqual(set(final["needs"]), set(jobs) - {"ci-gate"})
        self.assertEqual(final["if"], "${{ always() }}")
        self.assertEqual(final["steps"][-1]["run"].split()[2:], final["needs"])
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertIn("merge_group", workflow["on"])
        self.assertNotIn("pull_request_target", workflow["on"])
        for name, job in jobs.items():
            if name != "ci-gate":
                self.assertNotIn("if", job)
            self.assertNotIn("continue-on-error", job)
            for step in job["steps"]:
                self.assertNotIn("continue-on-error", step)
                if "uses" in step:
                    self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
