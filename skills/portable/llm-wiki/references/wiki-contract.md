# LLM Wiki Contract

Use this contract when creating or maintaining an LLM wiki. The wiki is
optimized for Obsidian review while remaining ordinary markdown.

## Directory structure

Default layout:

```text
raw/
  assets/
wiki/
  index.md
  log.md
  sources/
  entities/
  concepts/
  syntheses/
  questions/
```

- `raw/`: immutable source material. Do not edit or normalize source
  content after saving it.
- `raw/assets/`: source-adjacent images, attachments, and downloaded
  files.
- `wiki/index.md`: catalog of major pages, grouped by type.
- `wiki/log.md`: append-only activity log.
- `wiki/sources/`: one source summary per source.
- `wiki/entities/`: people, organizations, products, places, projects,
  and named systems.
- `wiki/concepts/`: reusable ideas, terms, methods, mechanisms, and
  patterns.
- `wiki/syntheses/`: cross-source essays, maps, comparisons, and
  durable conclusions.
- `wiki/questions/`: filed answers to recurring or important questions.

## Filenames and links

Use stable, human-readable filenames:

- lowercase words;
- hyphen separators;
- no dates unless the date is intrinsic to the source or event;
- keep names short enough to scan in Obsidian.

Use Obsidian wikilinks for internal links:

```markdown
[[retrieval-augmented-generation]]
[[source-karpathy-llm-wiki|Karpathy's LLM Wiki note]]
```

Use normal markdown links for external URLs and raw file paths:

```markdown
[raw transcript](../../raw/2026-04-19-interview.md)
```

Always compute raw-file links relative to the page being edited. From a
page under `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`,
`wiki/syntheses/`, or `wiki/questions/`, link to raw files with
`../../raw/...`. From `wiki/index.md` or `wiki/log.md`, use
`../raw/...`. Do not assume `raw/...` works from nested wiki pages.

Prefer aliases when they improve reading, not for every link.

## Frontmatter

Every generated wiki page should begin with YAML frontmatter:

```yaml
---
title: Example Page
type: concept
created: 2026-04-19
updated: 2026-04-19
sources:
  - "[[source-example]]"
tags:
  - concept
aliases:
  - Example
status: active
---
```

Source pages still use `sources: []` because they summarize a raw
source directly. Add provenance fields so the raw source remains
auditable:

```yaml
---
title: Example Source
type: source
created: 2026-04-19
updated: 2026-04-19
sources: []
source_type: article
raw_path: ../../raw/example-source.md
original_url: https://example.com/source
author: unknown
source_date: unknown
captured: 2026-04-19
tags:
  - source
aliases: []
status: active
---
```

Field rules:

- `title`: display title.
- `type`: one of `index`, `log`, `source`, `entity`, `concept`,
  `synthesis`, or `question`.
- `created`: date the wiki page was first created.
- `updated`: date the wiki page was last materially changed.
- `sources`: wikilinks to source pages supporting the page. Use `[]` for
  index, log, or unsourced stubs.
- `tags`: Dataview-friendly plain tag names without `#`.
- `aliases`: useful alternate names for Obsidian search and backlinks.
- `status`: `active`, `stub`, `needs-review`, `contradiction`, or
  `archived`.
- `source_type`: source-page field such as `article`, `paper`,
  `transcript`, `book`, `webpage`, `image`, `dataset`, or `unknown`.
- `raw_path`: source-page field linking to the immutable raw file using
  the correct relative path from the source page.
- `original_url`: source-page field for the original URL when known.
- `author`: source-page field for the author, organization, or origin
  when known; use `unknown` when the source does not provide it.
- `source_date`: source-page field for the date represented by the
  source when known; use `unknown` when unavailable.
- `captured`: source-page field for the date the source was saved or
  first ingested into the wiki.

Do not invent exact source dates, authors, or URLs. Use only metadata
present in the source or supplied by the user. Omit optional provenance
fields when they do not apply, except where the local wiki template
requires an explicit `unknown` value.

## Tags

Use these stable tag names:

- `source`
- `entity`
- `concept`
- `synthesis`
- `question`
- `contradiction`
- `stub`
- `needs-review`

Add domain tags sparingly when they will help browsing. Keep tags
lowercase and hyphenated.

## Page patterns

### Source pages

Place source pages in `wiki/sources/`. Recommended sections:

```markdown
## Summary
## Key Claims
## Evidence And Examples
## Important Terms
## Linked Pages
## Open Questions
```

Include a link to the raw file or original URL near the top. Summarize;
do not copy long passages. Use `sources: []` in frontmatter for source
pages and rely on `raw_path` plus optional provenance fields for the raw
source relationship.

### Entity pages

Place entity pages in `wiki/entities/`. Recommended sections:

```markdown
## Current Understanding
## Evidence
## Relationships
## Open Questions
```

Track name aliases in frontmatter. Link every major claim to at least
one source page.

### Concept pages

Place concept pages in `wiki/concepts/`. Recommended sections:

```markdown
## Definition
## How It Works
## Why It Matters
## Examples
## Related
```

Keep concepts reusable. If a concept grows into an argument across
multiple sources, create or update a synthesis page and link to it.

### Synthesis pages

Place synthesis pages in `wiki/syntheses/`. Recommended sections:

```markdown
## Claim
## Supporting Sources
## Tensions Or Contradictions
## Implications
## Open Questions
```

Mark unresolved disagreements explicitly with the `contradiction` or
`needs-review` tag.

### Question pages

Place filed answers in `wiki/questions/`. Recommended sections:

```markdown
## Question
## Answer
## Basis
## Follow-ups
```

Question pages should be short and link out to concepts, entities, and
syntheses rather than becoming duplicate topic pages.

## Index

`wiki/index.md` should be a compact map of the wiki:

```markdown
## Sources
## Concepts
## Entities
## Syntheses
## Questions
## Needs Review
```

List pages as wikilinks. Keep the index current after setup, ingest,
filing, and cleanup.

## Log

`wiki/log.md` is append-only. Add a new entry for every meaningful wiki
maintenance action:

```markdown
## [2026-04-19] ingest | Source Title

- Added: [[source-title]], [[concept-name]]
- Updated: [[related-entity]]
- Notes: flagged one contradiction about ...
```

Do not rewrite old log entries except to fix broken links introduced by
renaming pages.

## Maintenance rules

- Prefer one canonical page per concept, entity, or question.
- Merge duplicate pages by preserving the best title and adding aliases.
- Keep stubs useful: define what is missing and link to likely sources.
- Preserve contradictions. Do not resolve them by averaging or choosing
  a winner unless the sources justify that conclusion.
- Separate sourced claims from inference with clear wording.
- When local conventions conflict with this contract, preserve local
  conventions unless they weaken source immutability or traceability.
