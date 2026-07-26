# Capability review: skill-architect issue #29 pilot

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

## Question and component

The pilot tested whether the unprotected `source-links` component selected by
`## Sources` still earned activation context. The candidate removed only that
component. It saved 445 `SKILL.md` body characters and 445 runtime-package
bytes; the description and every protected component remained unchanged.

The review did not approve removal. No runtime reduction was applied.

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
| Repository | +2.27 pp | +10.23 pp | +50,097 | insufficient-evidence |
| Isolated | -3.41 pp | +14.77 pp | -241,651 | rejected |

Negative token reductions mean that the smaller candidate used more measured
input tokens in those stochastic runs. All six protected capability-review
checks passed on both repeats in both universes. Behavior evidence coverage
was below the configured 100% requirement in both cells (repository: 94.32%
Current, 96.59% Baseline, 97.73% Candidate; isolated: 96.59%, 96.59%, and
93.18%). Under the coverage gate that shortfall is `insufficient-evidence`,
not a Candidate rejection. The repository cell was otherwise close enough that
coverage incompleteness is what blocks approval there. Isolated also failed
quality non-inferiority and trigger-recall non-inferiority, so that cell stays
`rejected`.

The new trigger case passed at the configured threshold in both universes:
Current activated on 2/2 repository and 2/2 isolated repeats; Candidate
activated on 2/2 repository and 2/2 isolated repeats. The new behavior case
passed a focused Current diagnostic at 12/12 checks. In the complete repeated
matrix, Current passed all 24 checks for that case in each universe. Candidate
received 22 passes, one normal-check failure, and one unknown in repository,
and 22 passes plus two normal-check failures in isolation. Every protected
check for that case passed.

## Uncertainty and disposition

The review supports a useful bounded conclusion: `source-links` has measurable
static cost and its candidate was behaviorally close to Current, but evidence
coverage was incomplete and the isolated cell failed additional gates.
Repeated identical-package verification in the preceding local ablation run
also produced trigger and token variance, so the apparent marginal deltas are
not stable enough to justify removal.

The held-back labels are process controls; metrics remain whole-suite and do
not establish held-back-only non-inferiority. The observed frontier profile was
not selected. Codex evidence does not establish behavior in other harnesses.
This review does not support retirement and is not a human approval.

## Reproduce

Choose a `CANDIDATE_DIR` that does not exist, then construct the exact
`source-links` ablation candidate:

```bash
export CANDIDATE_DIR="${CANDIDATE_DIR:-.skill-evals/reproductions/issue-29-skill-architect}"
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

Verify the pinned runner and harness manifest before invoking models:

```bash
test "$(codex --version)" = "codex-cli 0.145.0"
PYTHONPATH=scripts python3 - <<'PY'
from pathlib import Path

from skill_eval.core import stable_digest

observed = stable_digest(Path("harnesses/codex.json"))
expected = "e2130ff78315e583d6dcdab463d95b51c31765dcfed4750b2bae06b923916bdd"
if observed != expected:
    raise SystemExit(f"harness digest mismatch: {observed}")
PY
```

Then run:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate "${CANDIDATE_DIR}" \
  --case-groups evals/skill-architect/capability-case-groups.json \
  --trigger-repeats 2 \
  --behavior-repeats 2 \
  --expected-current-digest ab6c13843ad75677897efe7fba2221de0b35562072ba7b139a8f1320b8d94ca9 \
  --expected-candidate-digest 4600559875b8798e36077be5160f1cf1b73cdb4c9ba831671cac1e243158066c \
  --expected-eval-digest 0c6a863b38c59c5d82577f3f68bd263acf0b6bff996c7aba2e68bd35e1b7dd4c \
  --expected-profiles-digest b44693bcb02699e664f7ce179af3acec1c4be78f9905bbc344e441359a6814d9 \
  --expected-case-groups-digest 386c91cf28a4e4df6ecdcf1c310dba306a4065200b9a65b895bfbc7ac98d31be
```
