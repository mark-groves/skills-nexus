# Capability review: issue #39 Sources rerun

- Evidence verdict: **rejected**
- Prepared disposition: **retain**
- Review status: **agent-prepared; pending maintainer review**
- Automatic promotion: disabled
- Required profile: `codex-supported-floor`
- Task model: `gpt-5.4`
- Judge model: `gpt-5.6-sol`
- Runner: `codex-cli 0.145.0`
- Universes: repository and isolated
- Repeats: trigger 2, behavior 2
- Case groups: `development` and `held-back-v1`

## Question and correction

This rerun repeated the issue #29 `source-links` experiment after issue #39
scoped trigger non-inferiority to canonical discovery-input changes. The
Candidate again removed only `## Sources`, saving 445 `SKILL.md` body
characters and 445 runtime-package bytes. Parsed frontmatter `name` and
`description` were identical to Current, so independent trigger differences
remained reported but were observational rather than blocking.

The corrected review did not approve removal. No runtime reduction was applied.

## Pinned evidence

| Input | SHA-256 |
| --- | --- |
| Current runtime | `ab6c13843ad75677897efe7fba2221de0b35562072ba7b139a8f1320b8d94ca9` |
| Candidate runtime | `4600559875b8798e36077be5160f1cf1b73cdb4c9ba831671cac1e243158066c` |
| Eval bundle | `0c6a863b38c59c5d82577f3f68bd263acf0b6bff996c7aba2e68bd35e1b7dd4c` |
| Eval specification | `027dc4f83ecdbf9ac613630b4589aad510e2107d4b59dadfe655953a621c8910` |
| Model profiles | `b44693bcb02699e664f7ce179af3acec1c4be78f9905bbc344e441359a6814d9` |
| Case groups | `386c91cf28a4e4df6ecdcf1c310dba306a4065200b9a65b895bfbc7ac98d31be` |
| Judge policy | `fb8c37fe58d9a79aa6cb9f3b167bac1b5a9125e5940ce8f469614d8cc007a510` |
| Codex harness manifest | `e2130ff78315e583d6dcdab463d95b51c31765dcfed4750b2bae06b923916bdd` |

## Results

| Universe | Candidate quality minus Current | Candidate lift over Baseline | Dynamic input-token reduction | Verdict |
| --- | ---: | ---: | ---: | --- |
| Repository | +5.68 pp | +15.91 pp | -57,919 | insufficient-evidence |
| Isolated | -4.55 pp | +10.23 pp | -59,901 | rejected |

Negative token reductions mean that the smaller Candidate used more measured
input tokens in these stochastic runs. All six protected capability-review
checks passed on both repeats in both universes.

Repository behavior evidence coverage was 98.86% for Current, Baseline, and
Candidate, below the configured 100% requirement. Its correctness, safety,
context, execution, judgment, fixture, repeat, suite, and discovery-scoped
trigger gates otherwise passed, so the cell remained
`insufficient-evidence`.

Isolated behavior evidence coverage was 73.86% for Current and Candidate and
71.59% for Baseline. Four of fourteen condition-blind judge turns failed
because the pinned judge model reported that it was at capacity. Task and
trigger runs had zero execution failures, but judgment completeness correctly
failed and the cell was `rejected`. Capacity failures are incomplete evidence,
not evidence that removing Sources caused behavioral harm.

## Trigger scope

The evaluator recorded `candidate_discovery.changed: false` and
`trigger_gate_mode: observational` in both cells. Repository recall was 100%
and specificity was 60% for both Current and Candidate. Isolated recall was
87.5% Current and 100% Candidate; specificity was 80% for both. Individual
independent trials still varied despite identical discovery inputs, directly
exercising the issue #39 distinction without weakening complete trigger-suite,
repeat, or execution requirements.

## Conclusion

The correction removes the unsupported trigger-causality claim from this
body-only experiment, but it does not establish that Sources is safe to remove.
Evidence coverage was incomplete, four isolated judgments were unavailable,
and dynamic input-token use was worse in both cells. Under the existing
fail-closed policy, retain `source-links`. This result neither proves the
component harmful nor authorizes promotion.

## Reproduce

Choose a `CANDIDATE_DIR` that does not exist, then construct the exact
`source-links` ablation Candidate:

```bash
export CANDIDATE_DIR="${CANDIDATE_DIR:-.skill-evals/reproductions/issue-39-sources-rerun}"
PYTHONPATH=scripts python3 - <<'PY'
import os
from pathlib import Path

from skill_review.ablation import create_component_candidate, load_component_contract

repo = Path.cwd()
skill = repo / "skills" / "skill-architect"
candidate = Path(os.environ["CANDIDATE_DIR"])
contract = load_component_contract(
    repo / "evals" / "skill-architect" / "components.json",
    skill,
)
digest = create_component_candidate(skill, candidate, contract, {"source-links"})
expected = "4600559875b8798e36077be5160f1cf1b73cdb4c9ba831671cac1e243158066c"
if digest != expected:
    raise SystemExit(f"candidate digest mismatch: {digest}")
PY
```

Then run the complete required-profile matrix:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate "${CANDIDATE_DIR}" \
  --case-groups evals/skill-architect/capability-case-groups.json \
  --trigger-repeats 2 \
  --behavior-repeats 2 \
  --jobs 8 \
  --expected-current-digest ab6c13843ad75677897efe7fba2221de0b35562072ba7b139a8f1320b8d94ca9 \
  --expected-candidate-digest 4600559875b8798e36077be5160f1cf1b73cdb4c9ba831671cac1e243158066c \
  --expected-eval-digest 0c6a863b38c59c5d82577f3f68bd263acf0b6bff996c7aba2e68bd35e1b7dd4c \
  --expected-profiles-digest b44693bcb02699e664f7ce179af3acec1c4be78f9905bbc344e441359a6814d9 \
  --expected-case-groups-digest 386c91cf28a4e4df6ecdcf1c310dba306a4065200b9a65b895bfbc7ac98d31be
```
