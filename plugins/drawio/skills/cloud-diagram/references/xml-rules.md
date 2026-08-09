# draw.io XML Generation Rules

Mandatory rules for generating valid, professional `.drawio` files.
Every rule here addresses a known failure mode — do not skip any.

## File structure

Every `.drawio` file follows this exact skeleton:

```xml
<mxfile host="Skills Nexus" agent="Skills Nexus" type="device">
  <diagram name="Architecture" id="diagram-1">
    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="10"
        guides="1" tooltips="1" connect="1" arrows="1" fold="1"
        page="1" pageScale="1" pageWidth="1600" pageHeight="900"
        math="0" shadow="0" adaptiveColors="auto">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- All diagram cells go here with parent="1" -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

- Cells `id="0"` and `id="1"` are structural — always include them.
- All user cells set `parent="1"` unless inside a container.
- Use `adaptiveColors="auto"` for dark mode support.
- Use landscape orientation: `pageWidth="1600" pageHeight="900"`.
- For complex diagrams: `pageWidth="1900" pageHeight="1500"`.

## Cell IDs

Use descriptive string IDs, not numeric sequences:

| Good | Bad |
| ------ | ----- |
| `vpc-main` | `2` |
| `subnet-pub-1` | `3` |
| `ec2-web-1` | `4` |
| `edge-alb-to-ec2` | `5` |

Descriptive IDs make the XML human-readable and editable.

## Edge geometry (CRITICAL)

Every `<mxCell>` with `edge="1"` MUST contain a child
`<mxGeometry>` element. Self-closing edge cells render nothing.

**Correct:**

```xml
<mxCell id="edge-1" value="HTTPS:443" edge="1"
    source="alb-1" target="ec2-1" parent="1"
    style="edgeStyle=orthogonalEdgeStyle;rounded=1;">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

**Wrong — will silently fail:**

```xml
<mxCell id="edge-1" edge="1" source="alb-1" target="ec2-1"
    parent="1" style="edgeStyle=orthogonalEdgeStyle;" />
```

### Edge routing

Two edge styles, chosen by connection pattern:

- **`edgeStyle=orthogonalEdgeStyle;`** — point-to-point connections.
  Uses 90-degree bends. Add `rounded=0;` or `rounded=1;` per the
  provider shape catalog.
- **`edgeStyle=elbowEdgeStyle;elbow=vertical;`** — for fan-out and
  fan-in patterns (one source to multiple targets sharing a bus
  line). Produces cleaner routing for 1-to-many flows.

Additional routing properties:

- Add `jettySize=auto;` for better port spacing.
- Use `exitX`/`exitY` and `entryX`/`entryY` (values 0-1) to
  control connection points on shapes.
- Leave at least 20px of straight segment before arrowheads.

### Explicit waypoints

Add waypoints when automatic routing would overlap edges: fan-out
from a single source, parallel bus patterns, or avoiding crossings.

```xml
<mxCell id="edge-2" edge="1" source="a" target="b" parent="1"
    style="edgeStyle=orthogonalEdgeStyle;rounded=1;">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="300" y="150" />
      <mxPoint x="300" y="250" />
    </Array>
  </mxGeometry>
</mxCell>
```

## Labels

- **Follow the label format shown in the provider shape catalog.**
  Some providers require HTML labels (`html=1;` with HTML entities);
  others use plain text. The catalog is the authority.
- Use `whiteSpace=wrap;` in styles for text wrapping.
- Edge labels go in the `value` attribute.
- Include protocol and port on edges: `HTTPS:443`, `TCP:5432`.

## Spacing and layout

The provider template is the primary layout reference. These are
recommended defaults when no template guidance applies:

- **Minimum 200px horizontal gap** between sibling resources.
- **Minimum 120px vertical gap** between tiers/rows.
- **Container padding:** 40px on each side.
- Align all coordinates to 10px grid multiples.
- Canvas size: 1600x900 for simple diagrams, 1900x1500 for
  complex ones. Adjust `dx`/`dy` and `pageWidth`/`pageHeight`.

## Style strings

Semicolon-separated `key=value;` pairs. No spaces around `=`.
Always terminate with a semicolon.

```text
shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.lambda;fillColor=#ED7100;strokeColor=#ffffff;fontColor=#232F3E;fontSize=12;
```

Common properties:

| Property | Purpose | Example |
| ---------- | --------- | --------- |
| `fillColor` | Background | `#ED7100` |
| `strokeColor` | Border | `#ffffff` |
| `fontColor` | Text colour | `#232F3E` |
| `fontSize` | Text size | `12` |
| `fontStyle` | Bold=1, Italic=2 | `1` |
| `rounded` | Rounded corners | `1` |
| `dashed` | Dashed border | `1` |
| `whiteSpace` | Text wrap | `wrap` |
| `verticalLabelPosition` | Label position | `bottom` |
| `verticalAlign` | Label alignment | `top` |
| `align` | Horizontal alignment | `center` |
| `aspect` | Lock aspect ratio | `fixed` |
| `container` | Enable containment | `1` |

## XML escaping

Escape these characters in `value` attributes:

| Character | Escape |
| ----------- | -------- |
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |

Do not use double hyphens (`--`) in XML comments.

## Dark mode

The `adaptiveColors="auto"` on `<mxGraphModel>` enables automatic
colour inversion. Explicit colours get inverted automatically.
Use `light-dark(lightColor,darkColor)` only when the automatic
inverse is wrong.
