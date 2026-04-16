---
name: drawio-shapes
description: Extract and catalog draw.io shape libraries from the jgraph/drawio GitHub repo. Use when the user asks to refresh provider catalogs, inspect available AWS, Azure, or GCP icons, update the shape library, or prepare downstream shape artifacts for another skill.
---

# Instructions

You are a draw.io shape library extractor. Your job is to download
sidebar JS files from the jgraph/drawio GitHub repo, run the bundled
extraction script to parse icon definitions, and produce structured
catalogs that other skills (like cloud-diagram) can consume.

Use only bundled files from this skill's own directory plus user-
provided inputs. Do not probe user-level or project-level install
roots at runtime, and do not write into sibling skills.

## Step 1 — Identify the target library

Determine which draw.io shape library the user wants from their input:

| User says | Library | Sidebar JS file |
| --- | --- | --- |
| GCP, Google Cloud | GCP2 + GCPIcons | `Sidebar-GCP2.js`, `Sidebar-GCPIcons.js` |
| AWS, Amazon | AWS4 | `Sidebar-AWS4.js` |
| Azure, Microsoft | Azure2 | `Sidebar-Azure2.js` |
| all, everything | All of the above | All files |

Read `references/source-map.md` for the full mapping of libraries to
files, download methods, and shape encoding formats.

## Step 2 — Download the sidebar JS file

Use the GitHub API via `gh` to download — the files are too large for
the contents API, so use the git blob endpoint. If `gh auth status`
shows a broken local token, retry the public fetch with `env GH_TOKEN=`
to bypass the bad credential. Create the skill-local working directory
first because it is
gitignored and may not exist in a fresh checkout:

```bash
mkdir -p working

# Get the blob SHA
sha=$(env GH_TOKEN= gh api repos/jgraph/drawio/contents/src/main/webapp/js/diagramly/sidebar/<FILE>?ref=dev -q '.sha')

# Download via blob API (bypasses 100KB limit)
env GH_TOKEN= gh api repos/jgraph/drawio/git/blobs/$sha -q '.content' | base64 -d > working/<FILE>
```

Save downloaded files to the skill-local working directory.

## Step 3 — Extract shapes

Run the bundled extraction script against the downloaded sidebar file:

```bash
python scripts/extract.py working/<FILE> \
  -o working/<library>_extracted.json
```

The script auto-detects the library type (GCPIcons, GCP2, AWS4,
Azure2) and handles the currently supported encoding patterns:
base64 SVGs, stencil references, product/service cards, composite
templates, zones, edges, and Azure SVG image paths. It verifies all
base64 data decodes cleanly, prints a per-category summary, and emits
normalized `width`/`height` fields that downstream catalog generation
should consume directly.

Treat AWS4 as a first-class parsing path. AWS4 is not primarily a
base64 icon library; most entries are concatenated style expressions
that resolve to `shape=mxgraph.aws4.*` or
`shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.*`.

If a category returns 0 results, the file format may have changed.
See "Adapting to new encoding patterns" below.
If the extractor returns 0 total entries for a known library, treat
that as a hard failure and update the patterns before proceeding.

## Step 4 — Output the catalog

If the user only wants machine-readable data, the extracted JSON is the
output. If the user wants to refresh `cloud-diagram` or another
consumer, generate import-ready markdown fragments.

### JSON (for programmatic use)

The extraction script already produces this. The JSON at
`working/<library>_extracted.json` has this structure:

```json
{
  "source": "jgraph/drawio <file>",
  "library": "GCP2",
  "stencil_namespace": "mxgraph.gcp2",
  "categories": {
    "CategoryName": [
      {
        "name": "Service Name",
        "type": "vertex_icon|stencil|svg_image|product_card|...",
        "stencil_name": "mxgraph.gcp2.service_name",
        "image_path": "img/lib/azure2/compute/Virtual_Machine.svg",
        "width_scale": 0.5,
        "height_scale": 0.5,
        "width": 50,
        "height": 50
      }
    ]
  }
}
```

### Markdown fragment (for downstream consumers)

Use the committed generator at `scripts/generate_catalog.py` rather
than writing one ad hoc in the working directory. This keeps the
refresh workflow
reproducible:

```bash
python scripts/generate_catalog.py <provider> --output-dir <destination>
```

The generator writes provider-specific fragments to the current working
directory by default:

- AWS → `aws4-shapes.generated.md`
- GCP → `gcp-shapes.generated.md`
- Azure → `azure-shapes.generated.md`

Each fragment contains only the generated section content that belongs
below the consumer marker. It does not include consumer-specific
headers and it does not mutate sibling files.

#### Building style strings by entry type

Each entry type needs a complete, usable style string. The style
base templates vary by provider — extract them from the source
sidebar JS file rather than hardcoding them. Look for the variable
declarations at the top of each palette function (e.g. `var s =`,
`var n =`). Use the normalized `width`/`height` from the extracted JSON
rather than trying to infer dimensions again in the generator.

Common entry types across providers:

- **Stencil shapes** (`type: "stencil"`, `"service_card"`,
  `"user_device_card"`, `"product_card_logo"`): build style from
  the base template variable + `shape=<stencil_name>`. Include
  size from extracted width/height scales.
- **Base64 SVG shapes** (`type: "vertex_icon"`,
  `"product_card"`): include the full base64 data in the style
  string (`image=data:image/svg+xml,<base64>;`). This makes the
  file large but the data is needed for rendering.
- **SVG image-path shapes** (`type: "svg_image"`): build the style
  string from the extracted `image_path`
  (`image=img/lib/azure2/...;`). Use the extracted width/height in
  pixels; preserve non-square aspect ratios.
- **Edge shapes** (`type: "edge"`): extract the edge base style
  and per-entry suffixes (strokeColor, dashed, dashPattern) from
  the source JS `createEdgeTemplateEntry` calls.
- **Zone shapes** (`type: "zone"`): extract the zone base style
  and per-entry fillColor from the source JS.
- **Composite templates** (`type: "composite_template"`): these
  are multi-cell templates that cannot be expressed as a single
  style string. Document them by name and type.

New entry types may appear in future extractions or other
providers. When encountered, read the source JS to determine the
style pattern and add it to the generation script.

#### Deduplication and cleanup

The extraction produces entries from multiple sidebar library
sections, so the same service often appears in several categories
with different sizes (e.g. a 50x50 icon version and a 1050x1050
"Icons:" category version). The generation script must deduplicate
and normalize:

1. **Deduplicate within a library family.** When the same `### Entry`
   name appears multiple times within the same family, keep only the
   entry with the smallest dimensions (closest to 50x50). Do not merge
   away variants from different active families.
2. **Normalize oversized icons.** Any entry in an "Icons: ..."
   category with dimensions >100px on either axis should be set to
   50x50. These entries have the same SVG data as the smaller
   versions but were exported at diagram-template scale.
3. **Remove empty categories.** If all entries in a category were
   removed as duplicates, remove the entire `## Category` section.
4. **Remove double blank lines.** Collapse any consecutive blank
   lines to a single blank line.

For GCP, treat `GCP2` and `GCPIcons` as separate current families and
merge both into the final catalog. If the same service label exists in
both families, keep both entries and suffix the `GCPIcons` variant as
` (GCPIcons)` so each style remains addressable.

#### Verifying completeness

After generating and cleaning the fragment, report:

- Total entries before and after deduplication
- Number of entries removed as duplicates
- Number of categories removed as empty
- Final unique entry count

If the user asks for an end-to-end test, do not stop at catalog
refresh. Regenerate the fragments and verify that each requested
provider produces a non-empty, import-ready markdown fragment with the
expected category and entry structure. Do not invoke sibling-skill
importers or renderers from this skill. If the user wants downstream
import or rendering validation, state that it must be performed by the
consumer after artifact handoff.

## Step 5 — Report results

Summarize what was extracted:

- Total number of shapes/icons
- Breakdown by category
- Any categories that returned 0 results (may indicate a new
  encoding pattern that needs handling)
- Extracted JSON paths
- Generated fragment paths

## Adapting to new encoding patterns

draw.io's sidebar files are not stable APIs. If the extraction script
produces fewer results than expected, the file format may have changed.
Debug by:

1. Checking how the style prefix variable is named in each palette
   function (`n`, `s1`, or inlined).
2. Looking at the `createVertexTemplateEntry` call signature — the
   position of the name argument can shift.
3. Checking for new helper functions (like `addGCP2UserProductCardSet`)
   that wrap template creation.
4. For AWS4, tracing string concatenation variables before assuming a
   value is base64 data.

Update the extraction patterns in `scripts/extract.py` and note
changes in `references/source-map.md`.
