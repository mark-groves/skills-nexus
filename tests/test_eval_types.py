import json
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
TYPES_DIR = REPO_DIR / "docs" / "eval-types"

EXPECTED = {
    "harness-target-v1.schema.json": ("HarnessTarget v1", ["schema_version", "harness"]),
    "skill-variant-v1.schema.json": (
        "SkillVariant v1",
        ["schema_version", "role", "logical_skill_name", "digest_sha256"],
    ),
    "eval-case-v1.schema.json": (
        "EvalCase v1",
        ["schema_version", "skill_name", "case_id", "kind", "evals_json_digest_sha256"],
    ),
    "judge-rubric-v1.schema.json": ("JudgeRubric v1", ["schema_version", "criteria"]),
    "blinded-candidate-run-v1.schema.json": (
        "BlindedCandidateRun v1",
        ["schema_version", "admission", "pins", "outputs", "sanitized_label"],
    ),
    "evidence-summary-v1.schema.json": (
        "EvidenceSummary v1",
        [
            "schema_version",
            "skill_name",
            "mode",
            "aggregation",
            "verdict",
            "limits_held",
            "author",
            "notes",
        ],
    ),
}


class EvalTypeSchemaTests(unittest.TestCase):
    def test_six_domain_schemas_are_present_and_closed(self) -> None:
        names = sorted(path.name for path in TYPES_DIR.glob("*.schema.json"))
        self.assertEqual(names, sorted(EXPECTED))
        for name, (title, required) in EXPECTED.items():
            payload = json.loads((TYPES_DIR / name).read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], title)
            self.assertEqual(payload.get("additionalProperties"), False)
            self.assertEqual(payload["required"], required)
            if name == "harness-target-v1.schema.json":
                self.assertEqual(payload["properties"]["harness"]["const"], "cursor-cloud-agent")
            if name == "blinded-candidate-run-v1.schema.json":
                self.assertEqual(
                    payload["properties"]["pins"]["properties"]["harness"]["const"],
                    "cursor-cloud-agent",
                )
                self.assertEqual(
                    payload["properties"]["outputs"]["properties"]["declaration"]["enum"],
                    ["PASS", "ISSUES", "BLOCKED"],
                )
                self.assertEqual(
                    set(payload["properties"]["pins"]["required"]),
                    {
                        "logical_skill_name",
                        "skill_digest_sha256",
                        "plugin_digest_sha256",
                        "case_id",
                        "case_kind",
                        "evals_json_digest_sha256",
                        "git_sha",
                        "harness",
                        "model",
                        "variant_id",
                    },
                )


if __name__ == "__main__":
    unittest.main()
