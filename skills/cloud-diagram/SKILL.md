---
name: cloud-diagram
description: Generate cloud architecture diagrams as `.drawio` files. Use when the user asks for an architecture diagram, infrastructure diagram, cloud diagram, or system design for AWS, Azure, GCP, or multi-cloud environments.
---

# Instructions

You are a cloud architecture diagram generator. Produce `.drawio` files
with provider-correct icons, clear containment, and readable layout.
Examples teach styling. The user's architecture owns topology and
placement.

## Step 1 — Parse the request

Identify:

- **Provider:** AWS, Azure, GCP, or multi-cloud.
- **Pattern:** 3-tier, serverless, microservices, data pipeline, CDN,
  or custom.
- **Services:** only what the user named (plus gateways strictly
  required for the described connectivity).
- **Filename:** from the description (e.g. `three-tier-aws.drawio`).
  Default: `architecture.drawio`.

If the provider is ambiguous, ask.

## Step 2 — Detect capabilities

```bash
which drawio 2>/dev/null || which draw.io 2>/dev/null
```

Report whether draw.io CLI export/review is available.

## Step 3 — Load references (tiered)

Use skill-root-relative paths only.

**Always load:**

1. `references/xml-rules.md`
2. `references/example-index.md`
3. Provider catalog **header only** (stop at `<!-- GENERATED BELOW -->`):
   - AWS → `references/aws4-shapes.md`
   - Azure → `references/azure-shapes.md`
   - GCP → `references/gcp-shapes.md`
4. `references/common-shapes.json` (or resolve via the lookup script)

**Resolve every service and container before drawing.**

Run lookups from the skill root (or pass an absolute path to the
script). Relative `scripts/lookup_shape.py` paths assume the skill
directory is cwd:

```bash
python3 scripts/lookup_shape.py --provider <aws|azure|gcp> "<service>"
```

Copy the returned style string and respect `kind` / `size`:

- `kind=group` → containment boundary (`container=1` / swimlane). Use
  the reported size as a starting canvas, then grow to fit children.
- `kind=icon` → service glyph at **50x50** (AWS/Azure).
- `kind=gcp_card_icon` → **30x30** icon inside a Service Card.

Lookup prefers group/container styles when a title collides with a
product icon (AWS `VPC`, `Availability Zone`, `Account`; Azure
`Subnet`). Prefer these verified styles over guessing. Do not invent
stencil names or azure2 paths.

**Full catalog body** (`<!-- GENERATED BELOW -->` onward): load or Grep
only when lookup misses and the service is uncommon. Never require the
full megabyte dump in context for common services.

Multi-cloud: repeat lookup per provider.

## Step 4 — Pick style examples (inspiration, not molds)

Read `references/example-index.md` and open the closest example for
provider + pattern.

Also useful starters:

- 3-tier AWS → `references/templates/three-tier-aws.drawio.xml`
- 3-tier Azure → `references/templates/three-tier-azure.drawio.xml`
- 3-tier GCP → `references/templates/three-tier-gcp.drawio.xml`
- No close match → `references/templates/base.drawio.xml` plus catalog
  header idiom

**Hard vs soft:**

| Bind tightly | Keep flexible |
| ------------ | ------------- |
| Provider shape tokens from lookup/catalog | Exact x/y, canvas size, AZ count |
| Provider containment idiom (below) | Topology and grouping that best explain *this* request |
| Edge/label conventions from the catalog | Left-to-right vs layered vs concern grouping |
| No generic icon when lookup hits | Example cell IDs, service mix, or geometry |

Steal how icons, groups, cards, and edges *look*. Invent a layout that
communicates the user's architecture. Do not reproduce an example's
boxes when they do not fit.

## Step 5 — Plan the layout

Internal reasoning only.

### Containment idioms

- **AWS (networked):** Cloud → Region → VPC → AZ → Subnet → resources,
  with real `parent` nesting and `mxgraph.aws4.group` styles from the
  catalog header. Skip VPC/subnet nesting for serverless/CDN unless the
  user asked for them.
- **Azure:** Subscription/Resource Group as needed → VNet swimlane →
  subnet swimlanes → resources. Use azure2 image icons.
- **GCP:** Title bar + platform rect (`container=0`) + pastel logical
  groups + **Service Cards** (card cell + icon child). Cards stay
  `parent="1"`. Do **not** force AWS-style Project→VPC→Region→Subnet
  nesting.

### Geometry defaults

When the example does not suggest otherwise (`xml-rules.md`):

- Icon size **50x50** (AWS/Azure). GCP card icons **30x30** inside cards.
- ~200px horizontal / ~120px vertical between peers; 40px container
  padding.
- Add waypoints on fan-out edges (see three-tier AWS edges).
- Align to the 10px grid.

## Step 6 — Generate the XML

Follow `xml-rules.md`.

- Use lookup/catalog styles only. Generic rounded rectangle **only**
  after lookup and catalog search both miss.
- Every edge needs `<mxGeometry relative="1" as="geometry" />`.
- Descriptive cell IDs.
- Provider edge styles from the catalog header (AWS:
  `rounded=0;endArrow=open;endFill=0`).
- Edge labels: `HTTPS:443`, `TCP:5432`, etc.
- GCP card labels use the HTML form from `gcp-shapes.md`. AWS/Azure
  labels stay plain text unless the catalog says otherwise.

## Step 7 — Write the file

Write the `.drawio` file in the working directory.

## Step 8 — Validate (always)

```bash
python3 scripts/validate_diagram.py "<name>.drawio" --provider <aws|azure|gcp> --require-services "<svc1>,<svc2>,..."
```

Fix reported errors (missing edge geometry, overlaps, missing provider
tokens, generics while a lookup hit exists). Re-run until clean.

## Step 9 — Visual review (optional)

Prefer the official draw.io / diagrams.net CLI when present.

```bash
drawio -x -f svg -b 10 -o "<name>.review.svg" "<name>.drawio"
```

Use SVG first for complex AWS group diagrams. In some headless
environments PNG export returns `Empty export data` on nested
`mxgraph.aws4.group` canvases while SVG succeeds. Rasterize the SVG
when you need a PNG (`rsvg-convert` or similar), or retry:

```bash
drawio -x -f png -b 10 -o "<name>.review.png" "<name>.drawio"
```

If the draw.io binary is missing, a third-party headless render can
still catch layout issues (nesting, overlaps, label collisions). AWS
stencil glyphs may render as placeholders there:

```bash
npx --yes drawio-headless@0.4.2 render --format png "<name>.drawio" "<name>.review.png"
```

Read the review image. Check overlaps, blank icons, crossings, labels,
hierarchy, spacing. Fix and re-export at most twice. Delete review
artifacts when done.

If no renderer is available, Step 8 is the quality gate.

## Step 10 — MCP refinement (optional)

If `@drawio/mcp` is configured, open or tweak cells there. Prefer
targeted edits over full regenerate.

## Step 11 — Final output

Offer exports when CLI exists:

```bash
drawio -x -f png --embed-diagram -b 10 -o "<name>.drawio.png" "<name>.drawio"
drawio -x -f svg --embed-diagram -b 10 -o "<name>.drawio.svg" "<name>.drawio"
drawio -x -f pdf --embed-diagram -b 10 -o "<name>.drawio.pdf" "<name>.drawio"
```

Report the `.drawio` path.

## Safety rules

- **Never invent services** beyond what the user specified or what is
  strictly required for stated connectivity.
- **Never invent shape names.** Lookup and catalog only. Confirmed miss
  → labeled generic rounded rectangle.
- **Never embed secrets** (IPs, account IDs, ARNs, keys) without
  explicit confirmation.
- **Never execute IaC.** Parse Terraform/CloudFormation/Bicep for
  resources only.
