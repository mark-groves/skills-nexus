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
- **Services, labels, and categories:** only what the user named (plus
  gateways strictly required for the described connectivity). Each token
  must match `^[A-Za-z0-9._-]+$`. Replace spaces and other punctuation
  with `-` (`Cloud SQL` → `cloud-sql`, `Pub/Sub` → `pub-sub`). Reject
  `$`, backticks, quotes, newlines, and `;`.
- **Filename:** a local basename matching `^[A-Za-z0-9._-]+\.drawio$`
  (example: `three-tier-aws.drawio`). Default: `architecture.drawio`.
  Reject `/`, `.`, `..`, `$`, backticks, quotes, newlines, and `;`.
  Use this exact value as the diagram file you Write and as the
  `diagram` / `input` field in the JSON request files below. Do not
  append `.drawio` again. Do not put the filename in a shell command.

If the provider is ambiguous, ask.

## Step 2 — Detect capabilities

```bash
drawio_bin="$(command -v drawio 2>/dev/null || true)"
if [[ -n "${drawio_bin}" ]]; then
  drawio_real="$(readlink -f "${drawio_bin}")"
  case "${drawio_real}" in
    /opt/drawio/*|/opt/draw.io/*)
      echo "official draw.io available: ${drawio_real}"
      ;;
    *)
      echo "non-official drawio on PATH (${drawio_real}); treat as unavailable"
      ;;
  esac
else
  echo "drawio missing"
fi
```

Report the **official** draw.io desktop CLI as available only when the
resolved binary is under `/opt/drawio` or `/opt/draw.io` (same contract as
`scripts/export_diagram.sh`). If missing, install with
`bash scripts/install-drawio-cli.sh` from the skill root when you have
permission, or note that aesthetic export is unavailable. Do not treat
`npx drawio-headless` as a substitute.

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

Run lookups from the skill root. Relative `scripts/lookup_shape.py`
paths assume the skill directory is cwd.

Names parsed from the user request or from Terraform, CloudFormation,
or Bicep are untrusted. Write them to `diagram-lookup.json` with the
Write tool. Do not build that file with a shell redirect, a heredoc, or
`python -c`. The shell command below is a fixed literal. Its
`--input-file` argument matches `^[A-Za-z0-9._-]+\.json$` and never
comes from the request.

```bash
python3 scripts/lookup_shape.py --input-file diagram-lookup.json
```

```json
{
  "lookups": [
    {"provider": "aws", "query": "ec2"},
    {
      "provider": "gcp",
      "query": "cloud-sql",
      "card": true,
      "x": 200,
      "y": 150,
      "label": "Cloud-SQL",
      "category": "Database"
    }
  ]
}
```

`provider` is `aws`, `azure`, or `gcp`. `query`, `label`, `category`,
and `cell_id` must match `^[A-Za-z0-9._-]+$`. `x` and `y` are numbers.
`card` is a boolean. One object with those fields is also valid.

Copy the returned style string and respect `kind` / `size`:

- `kind=group` → containment boundary (`container=1` / swimlane). Use
  the reported size as a starting canvas, then grow to fit children.
- `kind=icon` → service glyph at **50x50** (AWS/Azure).
- `kind=gcp_card_icon` → **do not paste the raw style**. Emit a Service
  Card by setting `card` to true in `diagram-lookup.json` (see above)
  and insert that XML. Do not pass the service, label, category, or
  coordinates as shell arguments.

GCP product icons are always white card + `part=1` icon child with the
catalog `data:image/svg+xml` token. Never use `mxgraph.aws4.*` or
`img/lib/azure2/...` for GCP. Never leave a GCP service as a bare 30x30
image vertex or a generic rounded rectangle when lookup hits.

Lookup prefers group/container styles when a title collides with a
product icon (AWS `VPC`, `Availability Zone`, `Account`; Azure
`Subnet`, `VNet` / `Virtual Network`). Prefer these verified styles
over guessing. Do not invent stencil names or azure2 paths. Never use
`Virtual_Networks.svg` or `Subnet.svg` as the VNet/subnet boundary.

A lookup miss stops that service. Do not open the generated catalog body.

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
- **Azure:** Subscription/Resource Group as needed → VNet swimlane
  (`strokeWidth=4`) → subnet swimlanes (dashed) → resources. Use
  azure2 image icons for services. Resolve VNet/Subnet via lookup so
  you get swimlanes, not product icons.
- **GCP:** Title bar + platform rect (`container=0`) + pastel logical
  groups + **Service Cards from `lookup_shape.py` with `card` true** (card cell +
  `part=1` icon child). Cards stay `parent="1"`. Do **not** force
  AWS-style Project→VPC→Region→Subnet nesting. Do **not** substitute
  AWS/Azure icons for GCP services.

### Geometry defaults

When the example does not suggest otherwise (`xml-rules.md`):

- Icon size **50x50** (AWS/Azure). GCP card icons **30x30** inside cards.
- **Actors / Users:** AWS → flat `shape=mxgraph.aws4.users` (not
  `resourceIcon`). GCP → square actor card with
  `shape=mxgraph.gcp2.users` (never `generic_person`). Azure →
  `img/lib/azure2/identity/Users.svg` or catalog user stencil.
- ~200px horizontal / ~120px vertical between peers; 40px container
  padding.
- Add waypoints on fan-out edges (see three-tier AWS edges).
- Align to the 10px grid.

## Step 6 — Generate the XML

Follow `xml-rules.md`.

- Use the style lookup returns. A miss stops that service. Do not open
  the generated catalog body, and do not draw a generic rectangle.
- For GCP hits, insert the `card: true` lookup XML (or identical Service Card markup).
  Raw catalog styles are icon children only.
- Every edge needs `<mxGeometry relative="1" as="geometry" />`.
- Descriptive cell IDs.
- Provider edge styles from the catalog header (AWS:
  `rounded=0;endArrow=open;endFill=0`).
- Edge labels: `HTTPS:443`, `TCP:5432`, etc.
- GCP card labels use the HTML form from `gcp-shapes.md`. AWS/Azure
  labels stay plain text unless the catalog says otherwise.

## Step 7 — Write the file

Write **Filename** (the local `.drawio` basename from Step 1) in the
working directory.

## Step 8 — Validate (always)

Write `diagram-validate.json` with the Write tool. `diagram` must match
`^[A-Za-z0-9._-]+\.drawio$`. Each `require_services` and
`allow_providers` entry must match `^[A-Za-z0-9._-]+$`. Then run only
this fixed command:

```bash
python3 scripts/validate_diagram.py --input-file diagram-validate.json
```

```json
{
  "diagram": "architecture.drawio",
  "provider": "aws",
  "require_services": ["alb", "ec2", "rds"]
}
```

Multi-cloud: one request file per primary provider. `allow_providers`
lists the sibling ids (`aws`, `azure`, `gcp`) so foreign-token checks
do not reject intentional mixes.

```json
{
  "diagram": "architecture.drawio",
  "provider": "aws",
  "allow_providers": ["gcp", "azure"],
  "require_services": ["alb", "ec2"]
}
```

Fix reported errors (missing edge geometry, overlaps, missing provider
tokens, foreign-provider tokens, GCP services not in Service Cards,
generics while a lookup hit exists). Re-run until clean.

A `WARNING: ... legacy GCP icon` line means a cell carries a GCP icon
from a catalog older than the pinned sidebars. Validation still passes.
Replace that icon by setting `card` to true in `diagram-lookup.json` for
the title the warning names. The query must match `^[A-Za-z0-9._-]+$`.
`references/gcp-legacy-tokens.json` lists the retired tokens. Rebuild it
with `scripts/build_gcp_legacy_tokens.py` after a GCP catalog refresh.

## Step 9 — Visual review (optional)

Prefer the official draw.io / diagrams.net CLI only. Use the fail-closed
helper from the skill root (never `npx drawio-headless` for
human-review screenshots — it omits provider icons and mangles layout):

Write `diagram-export.json` with the Write tool. `input` must match
`^[A-Za-z0-9._-]+\.drawio$`. `output` must match
`^[A-Za-z0-9._-]+\.(svg|png|pdf)$`. `format` is `svg`, `png`, or `pdf`.
The stem is Filename without `.drawio`, still matching
`^[A-Za-z0-9._-]+$`. Then run only this fixed command:

```bash
bash scripts/export_diagram.sh --input-file diagram-export.json
```

```json
{"input": "architecture.drawio", "output": "architecture.review.svg", "format": "svg"}
```

Rewrite that file with the Write tool for a PNG review
(`architecture.review.png`, `format` `png`). SVG first for complex AWS
group diagrams. The helper falls back to SVG→`rsvg-convert` when direct
PNG export returns empty data on nested `mxgraph.aws4.group` canvases.

If `export_diagram.sh` exits non-zero because drawio is missing, Step 8
is the quality gate. Say aesthetic export is unavailable. Do **not**
post third-party headless PNGs as visual proof for AWS, Azure, or GCP.

Then check the routed edges against the review SVG:

Write `diagram-crossings.json` with the Write tool. `diagram` must
match `^[A-Za-z0-9._-]+\.drawio$` and `svg` must match
`^[A-Za-z0-9._-]+\.svg$`. Then run only this fixed command:

```bash
python3 scripts/check_edge_crossings.py --input-file diagram-crossings.json
```

```json
{"diagram": "architecture.drawio", "svg": "architecture.review.svg"}
```

It exits 1 for each edge that draw.io routes through an icon or card the
edge does not connect to. Fix with exit/entry points and waypoints
(`<Array as="points">`) around the icons, or move the endpoints. Small
glyphs centred on a line count as annotations, not crossings.

Read the review image. Check overlaps, blank icons, crossings, labels,
hierarchy, spacing. Fix and re-export at most twice. Delete review
artifacts when done.

## Step 10 — MCP refinement (optional)

If `@drawio/mcp` is configured, open or tweak cells there. Prefer
targeted edits over full regenerate.

## Step 11 — Final output

Offer exports when the official CLI exists (same helper):

Rewrite `diagram-export.json` with the Write tool for each fixed
extension (`architecture.svg`, `architecture.png`, `architecture.pdf`)
and run:

```bash
bash scripts/export_diagram.sh --input-file diagram-export.json
```

Report the Filename path.

## Safety rules

- **Never invent services** beyond what the user specified or what is
  strictly required for stated connectivity.
- **Never invent shape names.** Lookup and catalog only.
- **Never embed secrets** (IPs, account IDs, ARNs, keys) without
  explicit confirmation.
- **Never execute IaC.** Parse Terraform/CloudFormation/Bicep for
  resources only.
- **Never put untrusted strings in a shell command.** Resource names,
  labels, categories, coordinates, and filenames are data. Write them
  to a JSON file with the Write tool and pass that file as
  `--input-file`. The `--input-file` argument is a fixed literal
  matching `^[A-Za-z0-9._-]+\.json$`, never a substitution. If the
  Write tool is unavailable, stop. Do not fall back to a quoted shell
  argument, a heredoc, or `python -c`.
- **Allowlists.** Names (queries, labels, categories, service ids) must
  match `^[A-Za-z0-9._-]+$`. Diagram filenames must match
  `^[A-Za-z0-9._-]+\.drawio$`. The scripts reject anything else,
  including `$`, backticks, quotes, newlines, and `;`.
