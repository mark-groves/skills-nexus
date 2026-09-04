import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_DIR / "scripts"))

from eval_cases import (  # noqa: E402
    EvalError,
    discover_repository_skills,
    load_case_groups,
    load_component_contract,
    load_eval_spec,
    parse_review_policy,
    resolve_skill,
    runtime_skill_copy,
)


class EvalCatalogTests(unittest.TestCase):
    def test_behavior_checks_accept_legacy_strings_and_structured_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "demo"
            evals_root = root / "evals"
            eval_path = evals_root / "demo" / "evals.json"
            eval_path.parent.mkdir(parents=True)
            eval_path.write_text(
                json.dumps(
                    {
                        "skill_name": "demo",
                        "trigger_evals": [],
                        "behavior_evals": [
                            {
                                "id": "safe",
                                "prompt": "demo",
                                "expected_behavior": "works",
                                "fixtures": [],
                                "checks": [
                                    "Reports the result",
                                    {
                                        "id": "never-write-secret",
                                        "text": "Does not write a secret",
                                        "class": "safety",
                                        "gate": "hard",
                                    },
                                ],
                            }
                        ],
                        "review_policy": {
                            "minimum_repeats": {"trigger": 3},
                            "context": {"minimum_reductions": {"skill_md_body_characters": 25}},
                        },
                    }
                ),
                encoding="utf-8",
            )

            spec = load_eval_spec(skill_dir, evals_root)

        legacy, protected = spec.behavior_cases[0].checks
        self.assertEqual(legacy.id, "safe-check-1")
        self.assertEqual(legacy.check_class, "quality")
        self.assertEqual(legacy.gate, "normal")
        self.assertFalse(legacy.structured)
        self.assertEqual(
            protected.as_dict(),
            {
                "id": "never-write-secret",
                "text": "Does not write a secret",
                "class": "safety",
                "gate": "hard",
            },
        )
        self.assertIsNotNone(spec.review_policy)
        assert spec.review_policy is not None
        self.assertEqual(spec.review_policy.minimum_trigger_repeats, 3)
        self.assertEqual(spec.review_policy.minimum_behavior_repeats, 2)
        self.assertEqual(
            dict(spec.review_policy.minimum_context_reductions),
            {"skill_md_body_characters": 25},
        )

    def test_structured_check_ids_are_valid_and_unique_across_the_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            skill_dir = root / "demo"
            evals_root = root / "evals"
            eval_path = evals_root / "demo" / "evals.json"
            eval_path.parent.mkdir(parents=True)
            structured = {
                "id": "same-check",
                "text": "Works",
                "class": "local-contract",
                "gate": "hard",
            }
            eval_path.write_text(
                json.dumps(
                    {
                        "skill_name": "demo",
                        "trigger_evals": [],
                        "behavior_evals": [
                            {
                                "id": "one",
                                "prompt": "one",
                                "expected_behavior": "works",
                                "fixtures": [],
                                "checks": [structured],
                            },
                            {
                                "id": "two",
                                "prompt": "two",
                                "expected_behavior": "works",
                                "fixtures": [],
                                "checks": [structured],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                EvalError,
                "Duplicate structured behavior check id: same-check",
            ):
                load_eval_spec(skill_dir, evals_root)

            structured["id"] = "Not Stable"
            eval_path.write_text(
                json.dumps(
                    {
                        "skill_name": "demo",
                        "trigger_evals": [],
                        "behavior_evals": [
                            {
                                "id": "one",
                                "prompt": "one",
                                "expected_behavior": "works",
                                "fixtures": [],
                                "checks": [structured],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(EvalError, "stable lowercase kebab-case"):
                load_eval_spec(skill_dir, evals_root)

    def test_review_policy_rejects_implicit_or_invalid_thresholds(self) -> None:
        with self.assertRaisesRegex(EvalError, "positive integers"):
            parse_review_policy(
                {"context": {"minimum_reductions": {"skill_md_body_characters": 0}}}
            )
        with self.assertRaisesRegex(EvalError, "between 0 and 1"):
            parse_review_policy({"quality": {"non_inferiority_margin": 1.1}})
        with self.assertRaisesRegex(EvalError, "unexpected keys"):
            parse_review_policy({"quality": {"aggregate_score": 0.9}})

    def test_eval_ids_must_be_safe_path_segments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            evals_root = Path(temp_dir) / "evals"
            eval_path = evals_root / "demo" / "evals.json"
            eval_path.parent.mkdir(parents=True)
            for unsafe_id in ("../escape", "/tmp/escape", r"..\escape", ".", ".."):
                with self.subTest(unsafe_id=unsafe_id):
                    eval_path.write_text(
                        json.dumps(
                            {
                                "skill_name": "demo",
                                "trigger_evals": [
                                    {
                                        "id": unsafe_id,
                                        "query": "demo",
                                        "should_trigger": True,
                                    }
                                ],
                                "behavior_evals": [],
                            }
                        ),
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(EvalError, "safe path segment"):
                        load_eval_spec(skill_dir, evals_root)

    def test_empty_fixture_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "demo"
            evals_root = Path(temp_dir) / "evals"
            eval_path = evals_root / "demo" / "evals.json"
            eval_path.parent.mkdir(parents=True)
            eval_path.write_text(
                json.dumps(
                    {
                        "skill_name": "demo",
                        "trigger_evals": [],
                        "behavior_evals": [
                            {
                                "id": 1,
                                "prompt": "demo",
                                "expected_behavior": "works",
                                "fixtures": ["   "],
                                "checks": ["result exists"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(EvalError, "non-empty strings"):
                load_eval_spec(skill_dir, evals_root)

    def test_repository_discovery_excludes_skills_inside_eval_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            canonical = repo / "skills" / "canonical"
            peer = repo / "skills" / "peer"
            embedded = repo / "evals" / "canonical" / "fixtures" / "embedded"
            nested = repo / "skills" / "category" / "nested"
            canonical.mkdir(parents=True)
            embedded.mkdir(parents=True)
            peer.mkdir(parents=True)
            nested.mkdir(parents=True)
            (canonical / "SKILL.md").write_text("canonical", encoding="utf-8")
            (embedded / "SKILL.md").write_text("embedded", encoding="utf-8")
            (peer / "SKILL.md").write_text("peer", encoding="utf-8")
            (nested / "SKILL.md").write_text("nested", encoding="utf-8")

            discovered = discover_repository_skills(repo)

            self.assertEqual(set(discovered), {canonical.resolve(), peer.resolve()})
            self.assertNotIn(embedded.resolve(), discovered)
            self.assertNotIn(nested.resolve(), discovered)

    def test_repository_discovery_excludes_dot_prefixed_plugin_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            visible = repo / "plugins" / "drawio" / "skills" / "cloud-diagram"
            hidden = repo / "plugins" / ".scratch" / "skills" / "hidden-skill"
            visible.mkdir(parents=True)
            hidden.mkdir(parents=True)
            (visible / "SKILL.md").write_text("visible", encoding="utf-8")
            (hidden / "SKILL.md").write_text("hidden", encoding="utf-8")

            discovered = discover_repository_skills(repo)

            self.assertEqual(discovered, (visible.resolve(),))
            self.assertNotIn(hidden.resolve(), discovered)

    def test_runtime_skill_copy_preserves_canonical_runtime_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            (source / "references").mkdir(parents=True)
            (source / "working").mkdir()
            (source / "evals" / "fixtures").mkdir(parents=True)
            (source / "SKILL.md").write_text(
                "---\nname: source\ndescription: Example skill\n---\n\n# Skill\n",
                encoding="utf-8",
            )
            (source / "references" / "guide.md").write_text("guide", encoding="utf-8")
            (source / "working" / "scratch.txt").write_text("scratch", encoding="utf-8")
            (source / "evals" / "evals.json").write_text("{}", encoding="utf-8")
            (source / "evals" / "fixtures" / "secret.txt").write_text("withheld", encoding="utf-8")

            destination = root / "installed"
            runtime_skill_copy(source, destination)

            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertTrue((destination / "references" / "guide.md").is_file())
            self.assertFalse((destination / "working").exists())
            self.assertFalse((destination / "evals").exists())
            self.assertEqual(
                (destination / "SKILL.md").read_text(encoding="utf-8"),
                (source / "SKILL.md").read_text(encoding="utf-8"),
            )

    def test_runtime_skill_copy_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source"
            (source / "references").mkdir(parents=True)
            (source / "SKILL.md").write_text("# Skill\n", encoding="utf-8")
            outside = root / "answer.md"
            outside.write_text("external\n", encoding="utf-8")
            (source / "references" / "answer.md").symlink_to(outside)

            destination = root / "installed"
            with self.assertRaisesRegex(EvalError, "may not contain symlinks"):
                runtime_skill_copy(source, destination)

            self.assertFalse(destination.exists())

    def test_resolve_skill_accepts_plugin_short_name(self) -> None:
        skill_dir = resolve_skill(REPO_DIR, "commit")
        self.assertEqual(skill_dir.name, "commit")
        self.assertTrue((skill_dir / "SKILL.md").is_file())

    def test_checked_in_catalog_and_companions_load(self) -> None:
        skill_dir = resolve_skill(REPO_DIR, "commit")
        spec = load_eval_spec(skill_dir, REPO_DIR / "evals")
        groups = load_case_groups(
            REPO_DIR / "evals" / "commit" / "capability-case-groups.json",
            spec,
        )
        self.assertGreater(len(spec.trigger_cases), 0)
        self.assertGreater(len(spec.behavior_cases), 0)
        self.assertTrue(any(group.kind == "development" for group in groups))
        contract = load_component_contract(
            REPO_DIR / "evals" / "commit" / "components.json",
            skill_dir,
        )
        self.assertGreater(len(contract.components), 0)


if __name__ == "__main__":
    unittest.main()
