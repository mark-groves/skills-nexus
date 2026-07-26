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
| Eval bundle | `d19f645d66821c3c67e04ce93bd68349769bee956c5b9ca3730dcfc62687b8b6` |
| Eval specification | `a93b556b89d01c614514e8ade804e694d2919358149d72183c9abc7e811ec3fb` |
| Model profiles | `b44693bcb02699e664f7ce179af3acec1c4be78f9905bbc344e441359a6814d9` |
| Case groups | `598c9a09c73fbb0db2589fe9f33d5c7ee0484801c3eef28cd3dc233f31aa4107` |
| Judge policy | `fb8c37fe58d9a79aa6cb9f3b167bac1b5a9125e5940ce8f469614d8cc007a510` |
| Codex harness manifest | `e2130ff78315e583d6dcdab463d95b51c31765dcfed4750b2bae06b923916bdd` |

## Results

| Universe | Candidate quality minus Current | Candidate lift over Baseline | Dynamic input-token reduction | Verdict |
| --- | ---: | ---: | ---: | --- |
| Repository | -1.22 pp | +6.10 pp | -471,964 | rejected |
| Isolated | +2.44 pp | +21.95 pp | -166,792 | rejected |

Negative token reductions mean that the smaller candidate used more measured
input tokens in those stochastic runs. All three protected capability-review
checks passed in both universes. The blocking gate was behavior evidence
coverage: repository coverage was 96.34% for Current and Candidate and 93.90%
for Baseline; isolated coverage was 95.12%, 93.90%, and 90.24% respectively,
below the configured 100% requirement.

The new trigger case passed at the configured threshold in both universes:
Current activated on 2/2 repository and 2/2 isolated repeats; Candidate
activated on 1/2 repository and 2/2 isolated repeats. The new behavior case
passed a focused Current diagnostic at 9/9 checks. In the complete repeated
matrix, Current received 17 passes plus one unknown in repository and 17 passes
plus one normal-check failure in isolation; Candidate received 17 passes plus
one unknown in repository and 18/18 passes in isolation. Every protected check
for that case passed.

## Uncertainty and disposition

The review supports a useful bounded conclusion: `source-links` has measurable
static cost and its candidate was behaviorally close to Current, but the
configured evidence-integrity bar was not met. Repeated identical-package
verification in the preceding local ablation run also produced trigger and
token variance, so the apparent marginal deltas are not stable enough to
justify removal.

The held-back labels are process controls; metrics remain whole-suite and do
not establish held-back-only non-inferiority. The observed frontier profile was
not selected. Codex evidence does not establish behavior in other harnesses.
This review does not support retirement and is not a human approval.

## Reproduce

Set `CANDIDATE_DIR` to a publishable `skill-architect` package matching the
pinned Candidate digest, then run:

```bash
python3 scripts/review_skill_capability.py \
  --skill skill-architect \
  --candidate "${CANDIDATE_DIR}" \
  --case-groups evals/skill-architect/capability-case-groups.json \
  --trigger-repeats 2 \
  --behavior-repeats 2 \
  --expected-current-digest ab6c13843ad75677897efe7fba2221de0b35562072ba7b139a8f1320b8d94ca9 \
  --expected-candidate-digest 4600559875b8798e36077be5160f1cf1b73cdb4c9ba831671cac1e243158066c \
  --expected-eval-digest d19f645d66821c3c67e04ce93bd68349769bee956c5b9ca3730dcfc62687b8b6 \
  --expected-profiles-digest b44693bcb02699e664f7ce179af3acec1c4be78f9905bbc344e441359a6814d9 \
  --expected-case-groups-digest 598c9a09c73fbb0db2589fe9f33d5c7ee0484801c3eef28cd3dc233f31aa4107
```
