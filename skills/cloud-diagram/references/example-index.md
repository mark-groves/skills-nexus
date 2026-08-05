# Provider style examples (inspiration only)

These files show how each provider draws icons, groups, cards, and
edges. Load the closest match for look and feel. Invent a layout that
fits the user's architecture. Never copy example geometry, cell IDs,
or service inventory as required structure.

## How to use

1. Pick provider + rough pattern below.
2. Read that one example (or the three-tier starter) for styling.
3. Resolve every service with `scripts/lookup_shape.py`
   (GCP: add `--card` for paste-ready Service Cards).
4. Draw containment with the provider idiom in `SKILL.md` / catalogs.
5. Lay out for clarity. Examples do not constrain coordinates.

## AWS

| Pattern | Primary example | Also useful |
| ------- | --------------- | ----------- |
| 3-tier / networked web | `templates/three-tier-aws.drawio.xml` | `templates/aws/aws-template-example01.drawio` |
| Identity / data lake | `templates/aws/aws-template-example02.drawio` | |
| IoT / analytics hybrid | `templates/aws/aws-template-example03.drawio` | |
| Multi-account / org | `templates/aws/aws-template-example04.drawio` | |
| Event-driven / serverless | `templates/aws/aws-template-example05.drawio` | |
| Streaming / complex | `templates/aws/aws-template-example06.drawio` | |
| CDN / edge | (no dedicated file) | use catalog shapes; skip VPC unless requested |

AWS idiom: nested `mxgraph.aws4.group` containers, `resourceIcon` /
`resIcon` service icons at **50x50**, edges
`rounded=0;endArrow=open;endFill=0`. Prefer true `parent` nesting for
network boundaries.

## Azure

| Pattern | Primary example | Also useful |
| ------- | --------------- | ----------- |
| 3-tier / web app | `templates/three-tier-azure.drawio.xml` | (Azure has no extra example library yet) |
| Other patterns | three-tier for swimlane + azure2 icon styling | invent layout; keep azure2 SVG paths |

Azure idiom: swimlane containers, `image=img/lib/azure2/...` icons at
**50x50**, dashed subnet swimlanes, VNet `strokeWidth=4`.

## GCP

| Pattern | Primary example | Also useful |
| ------- | --------------- | ----------- |
| 3-tier / app | `templates/three-tier-gcp.drawio.xml` | `templates/gcp/gcp-template-example01.drawio` |
| Streaming / batch pipeline | `templates/gcp/gcp-template-example02.drawio` | `example08`, `example09` |
| CI/CD / zonal | `templates/gcp/gcp-template-example03.drawio` | |
| Analytics / DMP | `templates/gcp/gcp-template-example04.drawio` | |
| Gaming / media | `templates/gcp/gcp-template-example06.drawio` | `example10` |
| App Engine | `templates/gcp/gcp-template-example07.drawio` | |
| Hybrid / on-prem | `templates/gcp/gcp-template-example11.drawio` | |
| Content / retail | `templates/gcp/gcp-template-example12.drawio` | `example05` |

GCP idiom: **Service Cards** from
`lookup_shape.py --provider gcp --card` (white card + `part=1` icon
child with `data:image/svg+xml`), pastel logical groups, platform
rect with `container=0`, cards `parent="1"`. Do not nest
Project→VPC→Subnet like AWS. Never substitute aws4/azure2 icons.
HTML labels on card icon children are required.
