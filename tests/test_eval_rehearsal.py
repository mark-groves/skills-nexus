import json
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
SUMMARY = REPO_DIR / "evals" / "commit" / "reviews" / "prove-variant-draft-message.json"


class RehearsalSummaryTests(unittest.TestCase):
    def test_commit_draft_rehearsal_is_inconclusive(self) -> None:
        payload = json.loads(SUMMARY.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["skill_name"], "commit")
        self.assertEqual(payload["mode"], "prove-variant")
        self.assertEqual(payload["aggregation"], "rank-all")
        self.assertEqual(payload["verdict"], "inconclusive")
        self.assertIn("no-auto-promote", payload["limits_held"])
        self.assertEqual(payload["run_labels"], ["cedar", "maple"])


if __name__ == "__main__":
    unittest.main()
