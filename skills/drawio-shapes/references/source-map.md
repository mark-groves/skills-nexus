# draw.io Shape Library Source Map

Reference for where draw.io stores its cloud provider shape/stencil
libraries in the jgraph/drawio GitHub repo.

## Repository layout

All sidebar files live under:

```text
src/main/webapp/js/diagramly/sidebar/
```

Stencil XML files (vector path definitions) live under:

```text
src/main/webapp/stencils/
```

## Downloading files

Sidebar JS files are typically 200KB-600KB, exceeding the GitHub
contents API's 100KB limit. Use the git blob endpoint instead:

```bash
# Step 1: get the blob SHA
sha=$(env GH_TOKEN= gh api \
  "repos/jgraph/drawio/contents/src/main/webapp/js/diagramly/sidebar/<FILE>?ref=dev" \
  -q '.sha')

# Step 2: download via blob API (no size limit)
env GH_TOKEN= gh api "repos/jgraph/drawio/git/blobs/$sha" \
  -q '.content' | base64 -d > "working/<FILE>"
```

Write downloaded files into the skill-local working directory.

If `gh auth status` reports a broken local token, keep `env GH_TOKEN=`
in place for public-repo fetches so bad credentials do not poison
anonymous API access.

## GCP libraries

GCP has three generations of shape libraries in draw.io:

### GCPIcons (newest, current)

- **File:** `Sidebar-GCPIcons.js` (~229KB, ~800 lines)
- **Palette prefix:** `gcpicons`
- **Shape encoding:** Base64-encoded SVGs in style strings
- **Style variable names:** `n` (first category), `s1` (rest), or
  inlined
- **Style prefix pattern:**
  `editableCssRules=.*;html=1;shape=image;...;image=data:image/svg+xml,`
- **Template function:** `createVertexTemplateEntry()`
- **Categories:** 16 (AI/ML, API Management, Compute, Data Analytics,
  Databases, Developer Tools, Expanded Product Card Icons, Generic,
  Hybrid/Multi Cloud, Security, IoT, Management Tools, Migration,
  Networking, Open Source Icons, Storage)
- **Total icons:** ~139

### GCP2 (Google Cloud Platform, current)

- **File:** `Sidebar-GCP2.js` (~569KB, ~2400 lines)
- **Palette prefix:** `gcp2`
- **Shape encoding:** Mixed — base64 SVGs, `mxgraph.gcp2.*` stencil
  references, and composite multi-cell templates
- **Stencil XML:** `src/main/webapp/stencils/gcp2.xml` (monolithic
  file with vector path definitions for `shape=mxgraph.gcp2.*`
  references)
- **Shape renderer:** `src/main/webapp/shapes/mxGCP2.js`
- **Template functions:**
  - `createVertexTemplateEntry()` — standard icon entries
  - `addGCP2UserProductCardSet()` — service cards with icons
  - `addGCP2ServiceCard()` — service card stencils
  - `addGCP2UserDeviceCard()` — user/device stencils
  - `addGCP2ProductCardSet()` — logo-based product cards
  - `createEdgeTemplateEntry()` — path/connection styles
  - `createVertexTemplateFromCells()` — composite multi-cell
    templates
- **Categories:** 35 (Paths, Zones, Service Cards, User Device Cards,
  Compute, API Management, Security, Data Analytics, Data Transfer,
  Cloud AI, IoT, Databases, Storage, Management Tools, Networking,
  Developer Tools, Expanded Product Cards, Product Cards, General
  Icons, plus 16 "Icons" sub-palettes)
- **Total entries:** ~467

For `cloud-diagram`, treat `GCP2` and `GCPIcons` as the current GCP
surface and merge both into the final catalog. Do not drop cross-family
duplicates by raw name alone; preserve the visual variants.

### GCP (oldest, legacy)

- **File:** `Sidebar-GCP.js` (~5KB)
- **Stencil XMLs:** `src/main/webapp/stencils/gcp/*.xml` (10 category
  files: big_data, compute, developer_tools, extras,
  identity_and_security, machine_learning, management_tools,
  networking, product_cards, storage_databases)
- **Palette prefix:** `gcp`
- **Notes:** Mostly superseded by GCP2. Only defines product card
  palette in the JS; actual shapes are in the stencil XMLs.

## AWS library

### AWS4

- **File:** `Sidebar-AWS4.js`
- **Palette prefix:** `aws4`
- **Shape encoding:** Mostly resolved style-string expressions that
  expand to `shape=mxgraph.aws4.*` or
  `shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.*`
- **Stencil directory:** `src/main/webapp/stencils/aws4/`
- **Template functions:** `createVertexTemplateEntry()`,
  `addAWS4Palette()`, and various helper functions
- **Notes:** Treat AWS4 as its own parsing path. A naive "find base64"
  extractor will misread style suffixes as fake payloads.

### AWS3 / AWS3D (legacy)

- **Files:** `Sidebar-AWS3.js`, `Sidebar-AWS3D.js`
- **Notes:** Superseded by AWS4.

## Azure library

### Azure2

- **File:** `Sidebar-Azure2.js`
- **Palette prefix:** `azure2`
- **Shape encoding:** SVG image references
  (`img/lib/azure2/<category>/<Service>.svg`)
- **Template functions:** `createVertexTemplateEntry()`
- **Folder wiring:** top-level `addAzure2Palette()` passes each
  sub-palette a folder prefix via `s + '<category>/'`
- **Base size:** `var r = 400`; icon sizes are typically expressed as
  `r * <scale>` and should be converted back to pixel dimensions for
  catalogs

### Azure (legacy)

- **File:** `Sidebar-Azure.js`
- **Notes:** Superseded by Azure2.

## Shape encoding patterns

Across all sidebar files, icons are encoded in one of these ways:

### 1. Base64 SVG via variable

The style prefix is stored in a variable, and base64 SVG data is
concatenated:

```javascript
var n = 'editableCssRules=.*;html=1;shape=image;...;image=data:image/svg+xml,';
this.createVertexTemplateEntry(
    n + 'PHN2ZyB4bWxucz0i...==;',
    s * 0.2, s * 0.2, '', 'Service Name', ...);
```

Variable names vary: `n`, `s1`, or others.

### 2. Base64 SVG inlined

The full style string including the base64 data is written directly:

```javascript
this.createVertexTemplateEntry(
    'editableCssRules=.*;...;image=data:image/svg+xml,PHN2Zy...==;',
    s * 0.2, s * 0.2, '', 'Service Name', ...);
```

### 3. Stencil reference

References a shape defined in a separate stencil XML file:

```javascript
var n = 'sketch=0;...;shape=mxgraph.gcp2.';
this.createVertexTemplateEntry(
    n + 'compute_engine',
    s * 100, s * 100, null, 'Compute Engine', ...);
```

AWS4 often uses a style-expression variant rather than a bare stencil
suffix:

```javascript
var n = 'sketch=0;aspect=fixed;' + mxConstants.STYLE_SHAPE + '=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.';
this.createVertexTemplateEntry(
    n + 'ec2',
    w, h, '', 'Amazon EC2', null, null, this.getTagsForStencil(gn, '', 'ec2', 'Amazon EC2'));
```

### 4. SVG image path (Azure)

References an SVG file by path:

```javascript
this.createVertexTemplateEntry(
    style + 'image=img/lib/azure2/compute/Virtual_Machine.svg;',
    ...);
```

Azure also uses a folder-prefix variant where `s` already contains the
category path:

```javascript
this.addAzure2ComputePalette(gn, r, sb, s + 'compute/');
this.createVertexTemplateEntry(
    s + 'Virtual_Machine.svg;',
    r * 0.17, r * 0.17, '', 'Virtual Machine', ...);
```

### 5. Product card helpers

Wrapper functions that build composite shapes. The base64 SVG icon
is set in a variable just before the call:

```javascript
icon = 'PHN2Zy...==;';
this.addGCP2UserProductCardSet('Compute\nEngine', 130, 170, ...);
```

## Catalog generation notes

- The committed markdown generator lives at
  `scripts/generate_catalog.py` in the `drawio-shapes` skill
  directory.
- The generator writes import-ready fragments such as
  `aws4-shapes.generated.md`, `gcp-shapes.generated.md`, and
  `azure-shapes.generated.md`.
- Downstream import is owned by the consuming skill or repository.
  This skill stops at producing the fragment artifacts.
- Deduplicate repeated entries only within a single library family.
  For example, shrink duplicate `GCP2` icon variants down to one entry,
  but keep overlapping `GCPIcons` variants distinct.
