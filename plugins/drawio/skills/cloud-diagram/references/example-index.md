# Provider style examples

These three starters show how each provider draws icons, groups, cards,
and edges. Open the starter for the provider you are drawing. Invent a
layout that fits the user's architecture. Never copy starter geometry,
cell IDs, or service inventory as required structure.

## Starters

| Provider | Starter |
| -------- | ------- |
| AWS | `templates/three-tier-aws.drawio.xml` |
| Azure | `templates/three-tier-azure.drawio.xml` |
| GCP | `templates/three-tier-gcp.drawio.xml` |

Resolve every service with `scripts/lookup_shape.py`. For GCP, add
`--card` and paste the Service Card.

## AWS

Nested `mxgraph.aws4.group` containers. `resourceIcon` / `resIcon`
service icons at 50x50. Edges use `rounded=0;endArrow=open;endFill=0`.
Prefer true `parent` nesting for network boundaries.

## Azure

Swimlane containers from lookup. VNet uses `strokeWidth=4`. Subnet and
Resource Group are dashed. Service icons are `image=img/lib/azure2/...`
at 50x50. Never use `Virtual_Networks.svg` or `Subnet.svg` as the
network boundary. Users use `img/lib/azure2/identity/Users.svg`.

## GCP

Service Cards from `lookup_shape.py --provider gcp --card`. That is a
white card plus a `part=1` icon child with `data:image/svg+xml`. Cards
stay `parent="1"`. Do not nest Project, VPC, and Subnet like AWS. Never
substitute aws4 or azure2 icons.
