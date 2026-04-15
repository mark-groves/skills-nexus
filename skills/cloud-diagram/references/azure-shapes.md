# Azure Shape Catalog for draw.io

A complete catalog of 613 unique Azure2 service shapes for draw.io
diagram generation using SVG image references.

## Shape naming convention

Azure shapes in draw.io use SVG images from the `azure2` library. The
path pattern is:

```text
img/lib/azure2/<category>/<Service_Name>.svg
```

- **Category** names are lowercase with underscores (e.g.,
  `ai_machine_learning`, `management_governance`).
- **Service** names use Title_Case with underscores (e.g.,
  `Virtual_Machine`, `Load_Balancers`).

The full list of azure2 category folders:

| Folder | Description |
| ------ | ----------- |
| `ai_machine_learning` | AI and ML services |
| `analytics` | Analytics and Synapse |
| `app_services` | App Service plans and apps |
| `compute` | VMs, VMSS, Batch, etc. |
| `containers` | AKS, ACI, Container Registry |
| `databases` | SQL, Cosmos DB, caches |
| `devops` | DevOps, DevTest Labs |
| `general` | General-purpose icons |
| `identity` | AAD, Entra, managed identity |
| `integration` | API Management, Service Bus |
| `iot` | IoT Hub, IoT Central |
| `management_governance` | Monitor, Policy, Arc |
| `networking` | VNets, load balancers, DNS |
| `other` | Miscellaneous services |
| `security` | Key Vault, Sentinel, Defender |
| `storage` | Storage accounts, Data Lake |
| `web` | SignalR, Notification Hubs |

To derive a path for a service not listed in this catalog:

1. Identify the category folder that best matches the service domain.
2. Convert the service name to Title_Case with underscores.
3. Construct the path: `img/lib/azure2/<category>/<Service_Name>.svg`.
4. If the icon does not render, try alternate category folders or
   check the draw.io azure2 library for the exact filename.

The base style string for all service icons is:

```text
aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/<category>/<Service_Name>.svg;
```

Add label positioning with:

```text
verticalLabelPosition=bottom;verticalAlign=top;
```

## Group and container styles

All groups use swimlane containers. The base swimlane pattern is:

```text
swimlane;startSize=30;fillColor=none;strokeColor=#COLOUR;dashed=0;container=1;collapsible=0;pointerEvents=0;fontColor=#333333;fontSize=12;fontStyle=1;
```

### Subscription

Solid border in Azure blue, label at top.

- **Style:** `swimlane;startSize=30;fillColor=none;strokeColor=#0078D4;dashed=0;container=1;collapsible=0;pointerEvents=0;fontColor=#0078D4;fontSize=14;fontStyle=1;`
- **Size:** 800x500 (adjust to content)

### Resource Group

Dashed grey border.

- **Style:** `swimlane;startSize=30;fillColor=none;strokeColor=#CBCBCB;dashed=1;dashPattern=5 5;container=1;collapsible=0;pointerEvents=0;fontColor=#333333;fontSize=12;fontStyle=1;`
- **Size:** 600x400 (adjust to content)

### Virtual Network (VNet)

Solid border in network blue with thick stroke.

- **Style:** `swimlane;startSize=30;fillColor=none;strokeColor=#3B8BBA;strokeWidth=4;dashed=0;container=1;collapsible=0;pointerEvents=0;fontColor=#3B8BBA;fontSize=12;fontStyle=1;`
- **Size:** 500x350 (adjust to content)

### Subnet

Dashed border in network blue.

- **Style:** `swimlane;startSize=30;fillColor=none;strokeColor=#3B8BBA;dashed=1;dashPattern=5 5;container=1;collapsible=0;pointerEvents=0;fontColor=#3B8BBA;fontSize=12;fontStyle=1;`
- **Size:** 400x250 (adjust to content)

### Region

Dashed border with label.

- **Style:** `swimlane;startSize=30;fillColor=none;strokeColor=#808080;dashed=1;dashPattern=8 4;container=1;collapsible=0;pointerEvents=0;fontColor=#808080;fontSize=12;fontStyle=1;`
- **Size:** 900x600 (adjust to content)

## Edge style

Preferred style:

```text
edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;
labelBackgroundColor=none;jettySize=auto;orthogonalLoop=1;
strokeColor=#333333;strokeWidth=1;fontSize=11;
```

- See `references/templates/three-tier-azure.drawio.xml` as a
  style reference.

<!-- GENERATED BELOW -->

## AI and ML

### AI Studio

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/AI_Studio.svg;`
- **Size:** 64x68

### Anomaly Detector

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Anomaly_Detector.svg;`
- **Size:** 68x68

### Applied AI

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Azure_Applied_AI.svg;`
- **Size:** 68x52

### Batch AI

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Batch_AI.svg;`
- **Size:** 48x68

### Bonsai

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Bonsai.svg;`
- **Size:** 68x66

### Bot Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Bot_Services.svg;`
- **Size:** 68x68

### Computer Vision

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Computer_Vision.svg;`
- **Size:** 68x68

### Cognitive Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Cognitive_Services.svg;`
- **Size:** 68x48

### Content Moderators

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Content_Moderators.svg;`
- **Size:** 68x63

### Custom Vision

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Custom_Vision.svg;`
- **Size:** 68x68

### Experimentation Studio

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Azure_Experimentation_Studio.svg;`
- **Size:** 68x56

### Face APIs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Face_APIs.svg;`
- **Size:** 68x68

### Form Recognizers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Form_Recognizers.svg;`
- **Size:** 63x68

### Genomics

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Genomics.svg;`
- **Size:** 36x68

### Immersive Readers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Immersive_Readers.svg;`
- **Size:** 68x68

### Language

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Language_Services.svg;`
- **Size:** 68x68

### Cognitive Services Decisions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Cognitive_Services_Decisions.svg;`
- **Size:** 68x68

### Content Safety

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Content_Safety.svg;`
- **Size:** 68x68

### Language Understanding

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Language_Understanding.svg;`
- **Size:** 68x68

### Machine Learning

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Machine_Learning.svg;`
- **Size:** 64x68

### Machine Learning Studio - Classic Web Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Machine_Learning_Studio_Classic_Web_Services.svg;`
- **Size:** 68x68

### Machine Learning Studio - Web Service Plans

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Machine_Learning_Studio_Web_Service_Plans.svg;`
- **Size:** 68x68

### Machine Learning Studio - Workspaces

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Machine_Learning_Studio_Workspaces.svg;`
- **Size:** 68x68

### Object Understanding

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Azure_Object_Understanding.svg;`
- **Size:** 68x68

### OpenAI

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Azure_OpenAI.svg;`
- **Size:** 68x68

### Personalizers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Personalizers.svg;`
- **Size:** 68x55

### QnA Makers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/QnA_Makers.svg;`
- **Size:** 68x68

### Serverless Search

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Serverless_Search.svg;`
- **Size:** 68x68

### Speech Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Speech_Services.svg;`
- **Size:** 68x68

### Translator Text

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/ai_machine_learning/Translator_Text.svg;`
- **Size:** 68x68

### Cognitive Search

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/Search_Services.svg;`
- **Size:** 68x49

### Metrics Advisor

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Metrics_Advisor.svg;`
- **Size:** 55x68

## Analytics

### Analysis Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Analysis_Services.svg;`
- **Size:** 63x48

### Data Lake Analytics

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Data_Lake_Analytics.svg;`
- **Size:** 68x68

### Data Lake Store Gen1

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Data_Lake_Store_Gen1.svg;`
- **Size:** 64x52

### Databricks

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Azure_Databricks.svg;`
- **Size:** 63x68

### Endpoint Analytics

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Endpoint_Analytics.svg;`
- **Size:** 68x68

### Event Hub Clusters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Event_Hub_Clusters.svg;`
- **Size:** 64x52

### Event Hubs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Event_Hubs.svg;`
- **Size:** 67x60

### HD Insight Clusters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/HD_Insight_Clusters.svg;`
- **Size:** 63x62

### Log Analytics Workspaces

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Log_Analytics_Workspaces.svg;`
- **Size:** 64x64

### Power BI Embedded

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Power_BI_Embedded.svg;`
- **Size:** 51x68

### Power Platform

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Power_Platform.svg;`
- **Size:** 65x68

### Stream Analytics Jobs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Stream_Analytics_Jobs.svg;`
- **Size:** 68x58

### Synapse Analytics

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/analytics/Azure_Synapse_Analytics.svg;`
- **Size:** 60x69

### Data Explorer Clusters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Data_Explorer_Clusters.svg;`
- **Size:** 68x68

### Data Factories

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Data_Factory.svg;`
- **Size:** 68x68

### Private Link Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Private_Link_Hub.svg;`
- **Size:** 59x68

## App Services

### API Management Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/API_Management_Services.svg;`
- **Size:** 65x60

### App Service Domains

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/App_Service_Domains.svg;`
- **Size:** 65x52

### App Service Environments

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/App_Service_Environments.svg;`
- **Size:** 64x64

### App Service Plans

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/App_Service_Plans.svg;`
- **Size:** 64x64

### App Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/App_Services.svg;`
- **Size:** 64x64

### CDN Profiles

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/CDN_Profiles.svg;`
- **Size:** 68x40

### Notification Hubs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/Notification_Hubs.svg;`
- **Size:** 67x56

### Search Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/Search_Services.svg;`
- **Size:** 72x52

## Ecosystem

### Applens

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_ecosystem/Applens.svg;`
- **Size:** 68x68

### Collaborative Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_ecosystem/Collaborative_Service.svg;`
- **Size:** 68x67

### Hybrid Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_ecosystem/Azure_Hybrid_Center.svg;`
- **Size:** 68x48

## Azure Stack

### Capacity

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Capacity.svg;`
- **Size:** 63x68

### Infrastructure Backup

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Infrastructure_Backup.svg;`
- **Size:** 60x69

### Multi Tenancy

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Multi_Tenancy.svg;`
- **Size:** 68x65

### Offers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Offers.svg;`
- **Size:** 65x64

### Plans

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Plans.svg;`
- **Size:** 52x64

### Stack

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Azure_Stack.svg;`
- **Size:** 62x64

### Updates

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/Updates.svg;`
- **Size:** 68x67

### User Subscriptions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_stack/User_Subscriptions.svg;`
- **Size:** 68x66

## Azure VMware Solution

### AVS

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_vmware_solution/AVS.svg;`
- **Size:** 70x56

## Blockchain

### ABS Member

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/blockchain/ABS_Member.svg;`
- **Size:** 56x65

### Blockchain Applications

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/blockchain/Blockchain_Applications.svg;`
- **Size:** 48x68

### Blockchain Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/blockchain/Azure_Blockchain_Service.svg;`
- **Size:** 68x68

### Consortium

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/blockchain/Consortium.svg;`
- **Size:** 68x68

### Outbound Connection

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/blockchain/Outbound_Connection.svg;`
- **Size:** 71x64

### Token Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/blockchain/Azure_Token_Service.svg;`
- **Size:** 59x68

## Compute

### Application Group

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Application_Group.svg;`
- **Size:** 68x68

### Automanaged VM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Automanaged_VM.svg;`
- **Size:** 68x62

### Availability Sets

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Availability_Sets.svg;`
- **Size:** 68x68

### Batch Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Batch_Accounts.svg;`
- **Size:** 68x64

### Cloud Services (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Cloud_Services_Classic.svg;`
- **Size:** 72x52

### Compute Galleries

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Azure_Compute_Galleries.svg;`
- **Size:** 68x68

### Container Instances

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Container_Instances.svg;`
- **Size:** 64x68

### Container Services (deprecated)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Container_Services_Deprecated.svg;`
- **Size:** 68x60

### Disk Encryption Sets

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Disk_Encryption_Sets.svg;`
- **Size:** 68x68

### Disks

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Disks.svg;`
- **Size:** 57x56

### Disks Snapshots

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Disks_Snapshots.svg;`
- **Size:** 68x71

### Function Apps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Function_Apps.svg;`
- **Size:** 68x60

### Host Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Host_Groups.svg;`
- **Size:** 62x68

### Host Pools

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Host_Pools.svg;`
- **Size:** 68x68

### Hosts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Hosts.svg;`
- **Size:** 57x68

### Image Definitions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Image_Definitions.svg;`
- **Size:** 66x64

### Image Templates

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Image_Templates.svg;`
- **Size:** 68x60

### Image Versions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Image_Versions.svg;`
- **Size:** 67x64

### Images

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Images.svg;`
- **Size:** 69x64

### Kubernetes Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Kubernetes_Services.svg;`
- **Size:** 68x60

### Maintenance Configuration

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Maintenance_Configuration.svg;`
- **Size:** 68x64

### Managed Service Fabric

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Managed_Service_Fabric.svg;`
- **Size:** 68x66

### Mesh Applications

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Mesh_Applications.svg;`
- **Size:** 68x68

### OS Images (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/OS_Images_Classic.svg;`
- **Size:** 69x64

### Restore Points

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Restore_Points.svg;`
- **Size:** 68x67

### Restore Points Collections

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Restore_Points_Collections.svg;`
- **Size:** 68x56

### Service Fabric Clusters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Service_Fabric_Clusters.svg;`
- **Size:** 67x64

### Shared Image Galleries

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Shared_Image_Galleries.svg;`
- **Size:** 64x64

### Spring Cloud

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Azure_Spring_Cloud.svg;`
- **Size:** 68x68

### Virtual Machine

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Virtual_Machine.svg;`
- **Size:** 69x64

### Virtual Machines (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Virtual_Machines_Classic.svg;`
- **Size:** 69x64

### VM Images (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/VM_Images_Classic.svg;`
- **Size:** 69x64

### VM Scale Sets

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/VM_Scale_Sets.svg;`
- **Size:** 68x68

### Workspaces

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Workspaces.svg;`
- **Size:** 65x56

## Containers

### Container Registries

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/containers/Container_Registries.svg;`
- **Size:** 68x61

### Red Hat OpenShift

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/containers/Azure_Red_Hat_OpenShift.svg;`
- **Size:** 68x68

## CXP

### Elixir

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/cxp/Elixir.svg;`
- **Size:** 49x68

### Elixir Purple

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/cxp/Elixir_Purple.svg;`
- **Size:** 49x68

## Databases

### Cache Redis

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Cache_Redis.svg;`
- **Size:** 64x52

### Cosmos DB

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Cosmos_DB.svg;`
- **Size:** 64x64

### Data Factory

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Data_Factory.svg;`
- **Size:** 68x68

### Database MariaDB Server

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Database_MariaDB_Server.svg;`
- **Size:** 48x64

### Database Migration Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Database_Migration_Services.svg;`
- **Size:** 64x69

### Database MySQL Server

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Database_MySQL_Server.svg;`
- **Size:** 48x64

### Database PostgreSQL Server

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Database_PostgreSQL_Server.svg;`
- **Size:** 48x64

### Database PostgreSQL Server Group

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Database_PostgreSQL_Server_Group.svg;`
- **Size:** 60x68

### Elastic Job Agents

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Elastic_Job_Agents.svg;`
- **Size:** 64x64

### Instance Pools

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Instance_Pools.svg;`
- **Size:** 65x64

### Managed Database

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Managed_Database.svg;`
- **Size:** 68x64

### Oracle Database

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Oracle_Database.svg;`
- **Size:** 68x68

### Purview Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_Purview_Accounts.svg;`
- **Size:** 68x42

### SQL

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_SQL.svg;`
- **Size:** 64x46

### SQL Data Warehouses

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SQL_Data_Warehouses.svg;`
- **Size:** 64x65

### SQL Database

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SQL_Database.svg;`
- **Size:** 48x64

### SQL Edge

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_SQL_Edge.svg;`
- **Size:** 68x68

### SQL Elastic Pools

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SQL_Elastic_Pools.svg;`
- **Size:** 68x68

### SQL Managed Instance

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SQL_Managed_Instance.svg;`
- **Size:** 65x64

### SQL Server

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SQL_Server.svg;`
- **Size:** 68x68

### SQL Server Registries

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SQL_Server_Registries.svg;`
- **Size:** 68x62

### SQL Server Stretch Databases

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_SQL_Server_Stretch_Databases.svg;`
- **Size:** 64x65

### SQL VM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Azure_SQL_VM.svg;`
- **Size:** 64x60

### SSIS Lift and Shift IR

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/SSIS_Lift_And_Shift_IR.svg;`
- **Size:** 62x68

### Virtual Clusters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/databases/Virtual_Clusters.svg;`
- **Size:** 66x64

## DevOps

### API Connections

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/API_Connections.svg;`
- **Size:** 68x45

### Application Insights

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/Application_Insights.svg;`
- **Size:** 44x63

### Change Analysis

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/Change_Analysis.svg;`
- **Size:** 68x68

### CloudTest

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/CloudTest.svg;`
- **Size:** 59x68

### Code Optimization

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/Code_Optimization.svg;`
- **Size:** 68x68

### DevOps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/Azure_DevOps.svg;`
- **Size:** 64x64

### DevOps Starter

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/DevOps_Starter.svg;`
- **Size:** 68x64

### DevTest Labs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/DevTest_Labs.svg;`
- **Size:** 66x64

### Lab Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/Lab_Accounts.svg;`
- **Size:** 65x68

### Lab Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/devops/Lab_Services.svg;`
- **Size:** 66x64

### Load Testing

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Load_Testing.svg;`
- **Size:** 59x68

## General

### All Resources

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/All_Resources.svg;`
- **Size:** 64x64

### Backlog

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Backlog.svg;`
- **Size:** 68x60

### Biz Talk

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Biz_Talk.svg;`
- **Size:** 69x64

### Blob Block

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Blob_Block.svg;`
- **Size:** 65x52

### Blob Page

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Blob_Page.svg;`
- **Size:** 65x52

### Branch

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Branch.svg;`
- **Size:** 72x72

### Browser

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Browser.svg;`
- **Size:** 65x52

### Bug

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Bug.svg;`
- **Size:** 59x64

### Builds

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Builds.svg;`
- **Size:** 64x64

### Cache

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cache.svg;`
- **Size:** 64x64

### Code

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Code.svg;`
- **Size:** 64x52

### Commit

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Commit.svg;`
- **Size:** 72x68

### Controls

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Controls.svg;`
- **Size:** 56x69

### Controls Horizontal

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Controls_Horizontal.svg;`
- **Size:** 69x56

### Cost Alerts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cost_Alerts.svg;`
- **Size:** 67x56

### Cost Analysis

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cost_Analysis.svg;`
- **Size:** 60x70

### Cost Budgets

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cost_Budgets.svg;`
- **Size:** 67x68

### Cost Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cost_Management.svg;`
- **Size:** 67x60

### Cost Management and Billing

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cost_Management_and_Billing.svg;`
- **Size:** 68x68

### Counter

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Counter.svg;`
- **Size:** 64x52

### Cubes

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Cubes.svg;`
- **Size:** 67x68

### Dashboard

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Dashboard.svg;`
- **Size:** 68x48

### Dev Console

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Dev_Console.svg;`
- **Size:** 65x52

### Download

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Download.svg;`
- **Size:** 64x67

### Error

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Error.svg;`
- **Size:** 71x68

### Extensions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Extensions.svg;`
- **Size:** 65x64

### File

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/File.svg;`
- **Size:** 56x69

### Files

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Files.svg;`
- **Size:** 64x70

### Folder Blank

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Folder_Blank.svg;`
- **Size:** 69x56

### Folder Website

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Folder_Website.svg;`
- **Size:** 68x56

### Free Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Free_Services.svg;`
- **Size:** 68x63

### FTP

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/FTP.svg;`
- **Size:** 60x48

### Gear

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Gear.svg;`
- **Size:** 64x64

### Globe

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Globe.svg;`
- **Size:** 56x66

### Globe Error

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Globe_Error.svg;`
- **Size:** 56x66

### Globe Success

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Globe_Success.svg;`
- **Size:** 56x66

### Globe Warning

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Globe_Warning.svg;`
- **Size:** 56x66

### Guide

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Guide.svg;`
- **Size:** 68x68

### Heart

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Heart.svg;`
- **Size:** 64x60

### Help and Support

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Help_and_Support.svg;`
- **Size:** 56x69

### Image

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Image.svg;`
- **Size:** 64x44

### Information

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Information.svg;`
- **Size:** 64x64

### Input Output

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Input_Output.svg;`
- **Size:** 64x55

### Journey Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Journey_Hub.svg;`
- **Size:** 60x63

### Launch Portal

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Launch_Portal.svg;`
- **Size:** 68x67

### Learn

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Learn.svg;`
- **Size:** 48x70

### Load Test

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Load_Test.svg;`
- **Size:** 68x66

### Location

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Location.svg;`
- **Size:** 40x71

### Log Streaming

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Log_Streaming.svg;`
- **Size:** 56x67

### Management Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Management_Groups.svg;`
- **Size:** 66x64

### Management Portal

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Management_Portal.svg;`
- **Size:** 60x48

### Marketplace

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Marketplace.svg;`
- **Size:** 56x64

### Media

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Media.svg;`
- **Size:** 68x68

### Media File

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Media_File.svg;`
- **Size:** 52x64

### Mobile

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Mobile.svg;`
- **Size:** 40x67

### Mobile Engagement

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Mobile_Engagement.svg;`
- **Size:** 40x67

### Module

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Module.svg;`
- **Size:** 64x64

### Power

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Power.svg;`
- **Size:** 44x68

### Power Up

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Power_Up.svg;`
- **Size:** 68x68

### Powershell

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Powershell.svg;`
- **Size:** 65x52

### Preview

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Preview.svg;`
- **Size:** 44x64

### Preview Features

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Preview_Features.svg;`
- **Size:** 68x68

### Process Explorer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Process_Explorer.svg;`
- **Size:** 70x68

### Production Ready Database

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Production_Ready_Database.svg;`
- **Size:** 48x64

### Quickstart Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Quickstart_Center.svg;`
- **Size:** 68x68

### Recent

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Recent.svg;`
- **Size:** 68x68

### Reservations

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Reservations.svg;`
- **Size:** 68x68

### Resource Explorer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Resource_Explorer.svg;`
- **Size:** 68x56

### Resource Group List

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Resource_Group_List.svg;`
- **Size:** 68x67

### Resource Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Resource_Groups.svg;`
- **Size:** 68x64

### Resource Linked

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Resource_Linked.svg;`
- **Size:** 72x72

### Scale

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Scale.svg;`
- **Size:** 60x60

### Scheduler

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Scheduler.svg;`
- **Size:** 68x68

### Search

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Search.svg;`
- **Size:** 64x65

### Search Grid

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Search_Grid.svg;`
- **Size:** 68x67

### Server Farm

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Server_Farm.svg;`
- **Size:** 64x64

### Service Health

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Service_Health.svg;`
- **Size:** 68x64

### SSD

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/SSD.svg;`
- **Size:** 66x60

### Storage Azure Files

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Storage_Azure_Files.svg;`
- **Size:** 64x52

### Storage Container

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Storage_Container.svg;`
- **Size:** 64x52

### Storage Queue

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Storage_Queue.svg;`
- **Size:** 64x52

### Subscriptions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Subscriptions.svg;`
- **Size:** 44x71

### Table

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Table.svg;`
- **Size:** 64x52

### Tag

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Tag.svg;`
- **Size:** 68x67

### Tags

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Tags.svg;`
- **Size:** 60x65

### Templates

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Templates.svg;`
- **Size:** 56x68

### TFS VC Repository

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/TFS_VC_Repository.svg;`
- **Size:** 68x68

### Toolbox

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Toolbox.svg;`
- **Size:** 64x56

### Troubleshoot

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Troubleshoot.svg;`
- **Size:** 66x68

### Versions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Versions.svg;`
- **Size:** 62x60

### Web Slots

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Web_Slots.svg;`
- **Size:** 58x64

### Web Test

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Web_Test.svg;`
- **Size:** 72x72

### Website Power

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Website_Power.svg;`
- **Size:** 68x68

### Website Staging

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Website_Staging.svg;`
- **Size:** 64x70

### Workbooks

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Workbooks.svg;`
- **Size:** 60x65

### Workflow

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/general/Workflow.svg;`
- **Size:** 68x70

### Marketplace Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Marketplace_Management.svg;`
- **Size:** 58x68

## Hybrid and Multicloud

### Azure Operator 5G Core

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/hybrid_multicloud/Azure_Operator_5G_Core.svg;`
- **Size:** 68x45

### Azure Operator Insights

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/hybrid_multicloud/Azure_Operator_Insights.svg;`
- **Size:** 68x68

### Azure Operator Nexus

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/hybrid_multicloud/Azure_Operator_Nexus.svg;`
- **Size:** 68x68

### Azure Operator Service Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/hybrid_multicloud/Azure_Operator_Service_Manager.svg;`
- **Size:** 68x68

### Azure Programmable Connectivity

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/hybrid_multicloud/Azure_Programmable_Connectivity.svg;`
- **Size:** 68x68

## Identity

### Active Directory

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_Active_Directory.svg;`
- **Size:** 70x64

### Active Directory Connect Health

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Active_Directory_Connect_Health2.svg;`
- **Size:** 68x60

### AD B2C

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_AD_B2C.svg;`
- **Size:** 69x64

### AD Domain Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_AD_Domain_Services.svg;`
- **Size:** 70x64

### AD Identity Protection

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_AD_Identity_Protection.svg;`
- **Size:** 68x62

### AD Privilege Identity Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_AD_Privilege_Identity_Management.svg;`
- **Size:** 68x68

### Administrative Units

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Administrative_Units.svg;`
- **Size:** 68x68

### App Registrations

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/App_Registrations.svg;`
- **Size:** 63x64

### Azure AD B2C

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_AD_B2C2.svg;`
- **Size:** 68x60

### Custom Azure AD Roles

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Custom_Azure_AD_Roles.svg;`
- **Size:** 68x68

### Enterprise Applications

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Enterprise_Applications.svg;`
- **Size:** 64x64

### Entra Connect

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Connect.svg;`
- **Size:** 68x64

### Entra Domain Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Domain_Services.svg;`
- **Size:** 68x68

### Entra Global Secure Access

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Global_Secure_Access.svg;`
- **Size:** 68x68

### Entra ID Protection

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_ID_Protection.svg;`
- **Size:** 68x60

### Entra Internet Access

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Internet_Access.svg;`
- **Size:** 68x68

### Entra Managed Identities

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Managed_Identities.svg;`
- **Size:** 68x60

### Entra Private Access

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Private_Access.svg;`
- **Size:** 68x68

### Entra Privileged Identity Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Privileged_Identity_Management.svg;`
- **Size:** 68x68

### Entra Verified ID

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Entra_Verified_ID.svg;`
- **Size:** 68x60

### External Identities

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/External_Identities.svg;`
- **Size:** 62x68

### Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Groups.svg;`
- **Size:** 68x56

### Identity Governance

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Identity_Governance.svg;`
- **Size:** 64x64

### Information Protection

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Azure_Information_Protection.svg;`
- **Size:** 51x68

### Managed Identities

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Managed_Identities.svg;`
- **Size:** 68x66

### Multi-Factor Authentication

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Multi_Factor_Authentication.svg;`
- **Size:** 68x68

### PIM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/PIM.svg;`
- **Size:** 60x68

### Security

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Security.svg;`
- **Size:** 57x68

### Tenant Properties

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Tenant_Properties.svg;`
- **Size:** 68x48

### User Settings

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/User_Settings.svg;`
- **Size:** 68x57

### Users

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Users.svg;`
- **Size:** 64x70

### Verifiable Credentials

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Verifiable_Credentials.svg;`
- **Size:** 68x68

### Verification As A Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Verification_As_A_Service.svg;`
- **Size:** 68x68

## Integration

### API for FHIR

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Azure_API_for_FHIR.svg;`
- **Size:** 68x65

### App Configuration

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/App_Configuration.svg;`
- **Size:** 64x68

### Data Catalog

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Azure_Data_Catalog.svg;`
- **Size:** 60x67

### Event Grid Domains

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Event_Grid_Domains.svg;`
- **Size:** 67x60

### Event Grid Subscriptions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Event_Grid_Subscriptions.svg;`
- **Size:** 67x60

### Event Grid Topics

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Event_Grid_Topics.svg;`
- **Size:** 67x60

### Integration Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Integration_Accounts.svg;`
- **Size:** 64x64

### Integration Environments

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Integration_Environments.svg;`
- **Size:** 64x68

### Integration Service Environments

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Integration_Service_Environments.svg;`
- **Size:** 68x68

### Logic Apps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Logic_Apps.svg;`
- **Size:** 67x52

### Logic Apps Custom Connector

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Logic_Apps_Custom_Connector.svg;`
- **Size:** 68x68

### Partner Namespace

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Partner_Namespace.svg;`
- **Size:** 68x61

### Partner Registration

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Partner_Registration.svg;`
- **Size:** 68x63

### Partner Topic

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Partner_Topic.svg;`
- **Size:** 68x61

### Relays

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Relays.svg;`
- **Size:** 67x60

### SendGrid Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/SendGrid_Accounts.svg;`
- **Size:** 67x68

### Service Bus

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Service_Bus.svg;`
- **Size:** 68x60

### Software as a Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/Software_as_a_Service.svg;`
- **Size:** 64x53

### System Topic

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/integration/System_Topic.svg;`
- **Size:** 68x60

### Databox Gateway

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Azure_Stack_Edge.svg;`
- **Size:** 68x48

### StorSimple Device Managers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/StorSimple_Device_Managers.svg;`
- **Size:** 70x64

## Intune

### AD Roles and Administrators

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Azure_AD_Roles_and_Administrators.svg;`
- **Size:** 64x64

### Client Apps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Client_Apps.svg;`
- **Size:** 68x68

### Device Compliance

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Device_Compliance.svg;`
- **Size:** 62x68

### Device Configuration

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Device_Configuration.svg;`
- **Size:** 62x68

### Device Enrollment

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Device_Enrollment.svg;`
- **Size:** 68x60

### Device Security Apple

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Device_Security_Apple.svg;`
- **Size:** 68x69

### Device Security Google

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Device_Security_Google.svg;`
- **Size:** 68x69

### Device Security Windows

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Device_Security_Windows.svg;`
- **Size:** 68x68

### Devices

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Devices.svg;`
- **Size:** 68x60

### eBooks

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/eBooks.svg;`
- **Size:** 68x60

### Exchange Access

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Exchange_Access.svg;`
- **Size:** 56x68

### Intune

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Intune.svg;`
- **Size:** 68x62

### Intune for Education

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Intune_For_Education.svg;`
- **Size:** 68x62

### Mindaro

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Mindaro.svg;`
- **Size:** 67x68

### Security Baselines

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Security_Baselines.svg;`
- **Size:** 68x68

### Software Updates

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Software_Updates.svg;`
- **Size:** 68x60

### Tenant Status

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/intune/Tenant_Status.svg;`
- **Size:** 64x68

## IoT

### Device Provisioning Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Device_Provisioning_Services.svg;`
- **Size:** 64x66

### Digital Twins

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Digital_Twins.svg;`
- **Size:** 68x68

### Industrial IoT

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Industrial_IoT.svg;`
- **Size:** 63x68

### IoT Central Applications

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/IoT_Central_Applications.svg;`
- **Size:** 60x69

### IoT Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/IoT_Hub.svg;`
- **Size:** 64x64

### IoT Operations

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Azure_IoT_Operations.svg;`
- **Size:** 68x64

### Maps Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Azure_Maps_Accounts.svg;`
- **Size:** 68x68

### Time Series Insights Environments

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Time_Series_Insights_Environments.svg;`
- **Size:** 67x68

### Time Series Insights Event Sources

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Time_Series_Insights_Event_Sources.svg;`
- **Size:** 67x68

### Windows10 Core Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Windows10_Core_Services.svg;`
- **Size:** 68x68

### Stack HCI Sizer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Azure_Stack_HCI_Sizer.svg;`
- **Size:** 68x68

### Stack HCI Premium

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/iot/Stack_HCI_Premium.svg;`
- **Size:** 68x68

### Time Series Insights Access Policies

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/internet_of_things/Time_Series_Insights_Access_Policies.svg;`
- **Size:** 42x68

## Management & Governance

### Activity Log

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Activity_Log.svg;`
- **Size:** 56x67

### Advisor

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Advisor.svg;`
- **Size:** 66x64

### Alerts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Alerts.svg;`
- **Size:** 67x56

### Arc

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Azure_Arc.svg;`
- **Size:** 69x52

### Arc Machines

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Arc_Machines.svg;`
- **Size:** 65x68

### Automation Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Automation_Accounts.svg;`
- **Size:** 68x68

### Blueprints

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Blueprints.svg;`
- **Size:** 65x64

### Compliance

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Compliance.svg;`
- **Size:** 52x64

### Customer Lockbox for MS Azure

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Customer_Lockbox_for_MS_Azure.svg;`
- **Size:** 68x66

### Diagnostics Settings

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Diagnostics_Settings.svg;`
- **Size:** 56x67

### Education

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Education.svg;`
- **Size:** 67x52

### Lighthouse

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Azure_Lighthouse.svg;`
- **Size:** 59x68

### MachinesAzureArc

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/MachinesAzureArc.svg;`
- **Size:** 44x68

### Managed Applications Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Managed_Applications_Center.svg;`
- **Size:** 68x54

### Managed Desktop

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Managed_Desktop.svg;`
- **Size:** 68x63

### Metrics

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Metrics.svg;`
- **Size:** 60x65

### Monitor

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Monitor.svg;`
- **Size:** 64x64

### My Customers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/My_Customers.svg;`
- **Size:** 69x56

### Operation Log (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Operation_Log_Classic.svg;`
- **Size:** 56x67

### Policy

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Policy.svg;`
- **Size:** 60x64

### Recovery Services Vaults

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Recovery_Services_Vaults.svg;`
- **Size:** 69x60

### Resource Graph Explorer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Resource_Graph_Explorer.svg;`
- **Size:** 67x64

### Resources Provider

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Resources_Provider.svg;`
- **Size:** 60x68

### Scheduler Job Collections

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Scheduler_Job_Collections.svg;`
- **Size:** 68x64

### Service Catalog MAD

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Service_Catalog_MAD.svg;`
- **Size:** 56x68

### Service Providers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Service_Providers.svg;`
- **Size:** 66x68

### Solutions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/solutions.svg;`
- **Size:** 64x64

### Universal Print

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/Universal_Print.svg;`
- **Size:** 68x58

### User Privacy

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/management_governance/User_Privacy.svg;`
- **Size:** 64x68

### Intune Trends

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Intune_Trends.svg;`
- **Size:** 57x68

## Menu

### Keys

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/menu/Keys.svg;`
- **Size:** 64x68

## Migrate

### Data Box

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/migrate/Data_Box.svg;`
- **Size:** 71x68

### Data Box Edge

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/migrate/Data_Box_Edge.svg;`
- **Size:** 67x48

### Migrate

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/migrate/Azure_Migrate.svg;`
- **Size:** 72x44

## Mixed Reality

### Remote Rendering

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/mixed_reality/Remote_Rendering.svg;`
- **Size:** 68x48

### Spatial Anchor Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/mixed_reality/Spatial_Anchor_Accounts.svg;`
- **Size:** 67x68

## Monitor

### SAP Azure Monitor

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/monitor/SAP_Azure_Monitor.svg;`
- **Size:** 70x56

## Networking

### Application Gateway Containers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Application_Gateway_Containers.svg;`
- **Size:** 68x64

### Application Gateways

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Application_Gateways.svg;`
- **Size:** 64x64

### ATM Multistack

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/ATM_Multistack.svg;`
- **Size:** 68x68

### Bastions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Bastions.svg;`
- **Size:** 58x68

### Communications Gateway

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Azure_Communications_Gateway.svg;`
- **Size:** 68x68

### Connections

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Connections.svg;`
- **Size:** 68x68

### DDoS Protection Plans

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/DDoS_Protection_Plans.svg;`
- **Size:** 56x68

### DNS Multistack

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/DNS_Multistack.svg;`
- **Size:** 68x68

### DNS Private Resolver

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/DNS_Private_Resolver.svg;`
- **Size:** 68x60

### DNS Security Policy

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/DNS_Security_Policy.svg;`
- **Size:** 68x68

### DNS Zones

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/DNS_Zones.svg;`
- **Size:** 64x64

### ExpressRoute Circuits

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/ExpressRoute_Circuits.svg;`
- **Size:** 70x64

### Firewall Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Azure_Firewall_Manager.svg;`
- **Size:** 70x60

### Firewall Policy

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Azure_Firewall_Policy.svg;`
- **Size:** 68x49

### Firewalls

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Firewalls.svg;`
- **Size:** 71x60

### Front Doors

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Front_Doors.svg;`
- **Size:** 68x60

### IP Address Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/IP_Address_Manager.svg;`
- **Size:** 68x60

### IP Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/IP_Groups.svg;`
- **Size:** 67x52

### Load Balancer Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Load_Balancer_Hub.svg;`
- **Size:** 54x68

### Load Balancers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Load_Balancers.svg;`
- **Size:** 72x72

### Local Network Gateways

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Local_Network_Gateways.svg;`
- **Size:** 68x68

### NAT

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/NAT.svg;`
- **Size:** 68x68

### Network Interfaces

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Network_Interfaces.svg;`
- **Size:** 68x60

### Network Security Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Network_Security_Groups.svg;`
- **Size:** 56x68

### Network Watcher

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Network_Watcher.svg;`
- **Size:** 64x64

### On Premises Data Gateways

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/On_Premises_Data_Gateways.svg;`
- **Size:** 68x65

### Private Endpoint

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Private_Endpoint.svg;`
- **Size:** 72x66

### Private Link

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Private_Link.svg;`
- **Size:** 72x66

### Private Link Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Private_Link_Hub.svg;`
- **Size:** 59x68

### Private Link Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Private_Link_Service.svg;`
- **Size:** 69x40

### Proximity Placement Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Proximity_Placement_Groups.svg;`
- **Size:** 72x68

### Public IP Addresses

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Public_IP_Addresses.svg;`
- **Size:** 65x52

### Public IP Addresses (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Public_IP_Addresses_Classic.svg;`
- **Size:** 64x52

### Public IP Prefixes

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Public_IP_Prefixes.svg;`
- **Size:** 72x56

### Reserved IP Addresses (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Reserved_IP_Addresses_Classic.svg;`
- **Size:** 68x55

### Resource Management Private Link

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Resource_Management_Private_Link.svg;`
- **Size:** 68x66

### Route Filters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Route_Filters.svg;`
- **Size:** 71x44

### Route Tables

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Route_Tables.svg;`
- **Size:** 64x62

### Service Endpoint Policies

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Service_Endpoint_Policies.svg;`
- **Size:** 62x64

### Spot VM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Spot_VM.svg;`
- **Size:** 68x63

### Spot VMSS

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Spot_VMSS.svg;`
- **Size:** 68x64

### Subnet

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Subnet.svg;`
- **Size:** 68x41

### Traffic Manager Profiles

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Traffic_Manager_Profiles.svg;`
- **Size:** 68x68

### Virtual Network Gateways

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Virtual_Network_Gateways.svg;`
- **Size:** 52x69

### Virtual Networks

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Virtual_Networks.svg;`
- **Size:** 67x40

### Virtual Networks (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Virtual_Networks_Classic.svg;`
- **Size:** 67x40

### Virtual Router

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Virtual_Router.svg;`
- **Size:** 68x68

### Virtual WAN Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Virtual_WAN_Hub.svg;`
- **Size:** 65x64

### Virtual WANs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Virtual_WANs.svg;`
- **Size:** 65x64

### Web Application Firewall Policies (WAF)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Web_Application_Firewall_Policies_WAF.svg;`
- **Size:** 68x68

### Connected Cache

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Connected_Cache.svg;`
- **Size:** 68x56

## Other

### A

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_A.svg;`
- **Size:** 68x64

### ACS Solutions Builder

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/ACS_Solutions_Builder.svg;`
- **Size:** 68x52

### AKS Automatic

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/AKS_Automatic.svg;`
- **Size:** 68x68

### AKS Istio

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/AKS_Istio.svg;`
- **Size:** 68x68

### API Proxy

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/API_Proxy.svg;`
- **Size:** 68x38

### App Compliance Automation

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/App_Compliance_Automation.svg;`
- **Size:** 68x49

### App Space Compoment

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/App_Space_Component.svg;`
- **Size:** 57x68

### Aquila

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Aquila.svg;`
- **Size:** 68x67

### Arc Data Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Arc_Data_Services.svg;`
- **Size:** 65x68

### Arc Kubernetes

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Arc_Kubernetes.svg;`
- **Size:** 68x68

### Arc PostgreSQL

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Arc_PostgreSQL.svg;`
- **Size:** 65x68

### Arc SQL Managed Instance

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Arc_SQL_Managed_Instance.svg;`
- **Size:** 65x68

### Arc SQL Server

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Arc_SQL_Server.svg;`
- **Size:** 65x68

### AVS VM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/AVS_VM.svg;`
- **Size:** 68x63

### AzureAttestation

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/AzureAttestation.svg;`
- **Size:** 56x68

### Azurite

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azurite.svg;`
- **Size:** 68x66

### Backup Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Backup_Center.svg;`
- **Size:** 68x62

### Backup Vault

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Backup_Vault.svg;`
- **Size:** 68x58

### Bare Metal Infrastructure

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Bare_Metal_Infrastructure.svg;`
- **Size:** 68x64

### Business Process Tracking

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Business_Process_Tracking.svg;`
- **Size:** 49x68

### Center for SAP

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Center_for_SAP.svg;`
- **Size:** 68x68

### Central Service Instance for SAP

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Central_Service_Instance_for_SAP.svg;`
- **Size:** 68x36

### Ceres

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Ceres.svg;`
- **Size:** 59x68

### Chaos Studio

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Chaos_Studio.svg;`
- **Size:** 68x68

### Cloud Services (extended support)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Cloud_Services_(extended_support).svg;`
- **Size:** 68x58

### Cloud Shell

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Cloud_Shell.svg;`
- **Size:** 68x47

### Communication Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Communication_Services.svg;`
- **Size:** 68x50

### Compliance Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Compliance_Center.svg;`
- **Size:** 68x68

### Compute Fleet

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Compute_Fleet.svg;`
- **Size:** 68x68

### Confidential_Ledger

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Confidential_Ledger.svg;`
- **Size:** 68x68

### Container App Environments

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Container_App_Environments.svg;`
- **Size:** 68x68

### Connected Vehicle Platform

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Connected_Vehicle_Platform.svg;`
- **Size:** 68x52

### Cost Export

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Cost_Export.svg;`
- **Size:** 68x53

### Custom IP Prefix

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Custom_IP_Prefix.svg;`
- **Size:** 68x68

### Dashboard Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Dashboard_Hub.svg;`
- **Size:** 68x52

### Data Collection Rules

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Data_Collection_Rules.svg;`
- **Size:** 67x68

### Database Instance for SAP

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Database_Instance_for_SAP.svg;`
- **Size:** 68x65

### Dedicated HSM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Dedicated_HSM.svg;`
- **Size:** 68x62

### Defender CM Local Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_CM_Local_Manager.svg;`
- **Size:** 68x68

### Defender DCS Controller

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_DCS_Controller.svg;`
- **Size:** 68x62

### Defender Distributer Control System

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Distributer_Control_System.svg;`
- **Size:** 68x68

### Defender Engineering Station

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Engineering_Station.svg;`
- **Size:** 68x63

### Defender External Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_External_Management.svg;`
- **Size:** 66x68

### Defender Freezer Monitor

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Freezer_Monitor.svg;`
- **Size:** 48x68

### Defender Historian

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Historian.svg;`
- **Size:** 68x67

### Defender HMI

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_HMI.svg;`
- **Size:** 68x53

### Defender Industrial Packaging System

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Industrial_Packaging_System.svg;`
- **Size:** 68x68

### Defender Industrial Printer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Industrial_Printer.svg;`
- **Size:** 68x68

### Defender Industrial Scale System

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Industrial_Scale_System.svg;`
- **Size:** 68x68

### Defender Industrial Robot

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Industrial_Robot.svg;`
- **Size:** 51x68

### Defender Marquee

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Marquee.svg;`
- **Size:** 68x41

### Defender Meter

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Meter.svg;`
- **Size:** 68x68

### Defender PLC

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_PLC.svg;`
- **Size:** 68x68

### Defender Pneumatic Device

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Pneumatic_Device.svg;`
- **Size:** 68x56

### Defender Programable Board

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Programable_Board.svg;`
- **Size:** 68x68

### Defender Relay

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Relay.svg;`
- **Size:** 68x27

### Defender Robot Controller

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Robot_Controller.svg;`
- **Size:** 66x68

### Defender RTU

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_RTU.svg;`
- **Size:** 68x60

### Defender Sensor

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Sensor.svg;`
- **Size:** 68x50

### Defender Slot

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Slot.svg;`
- **Size:** 68x68

### Defender Web Guiding System

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Defender_Web_Guiding_System.svg;`
- **Size:** 68x24

### Deployment Environments

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Deployment_Environments.svg;`
- **Size:** 68x65

### Detonation

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Detonation.svg;`
- **Size:** 62x64

### Device Update IoT Hub

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Device_Update_IoT_Hub.svg;`
- **Size:** 60x68

### Dev Tunnels

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Dev_Tunnels.svg;`
- **Size:** 68x68

### Disk Pool

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Disk_Pool.svg;`
- **Size:** 68x66

### Edge Hardware Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Edge_Hardware_Center.svg;`
- **Size:** 68x68

### Edge Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Edge_Management.svg;`
- **Size:** 66x68

### Elastic SAN

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Elastic_SAN.svg;`
- **Size:** 68x68

### Entra Connect Sync

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Entra_Connect_Sync.svg;`
- **Size:** 68x68

### Entra Identity

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Entra_Identity.svg;`
- **Size:** 68x60

### Exchange On Premises Access

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Exchange_On_Premises_Access.svg;`
- **Size:** 40x68

### Express Route Traffic Collector

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Express_Route_Traffic_Collector.svg;`
- **Size:** 58x68

### ExpressRoute Direct

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/ExpressRoute_Direct.svg;`
- **Size:** 68x60

### FHIR Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/FHIR_Service.svg;`
- **Size:** 68x59

### Fiji

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Fiji.svg;`
- **Size:** 54x68

### Grafana

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Grafana.svg;`
- **Size:** 68x53

### HDI AKS Cluster

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/HDI_AKS_Cluster.svg;`
- **Size:** 60x68

### HPC Workbench

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_HPC_Workbench.svg;`
- **Size:** 56x68

### IcM Troubleshooting

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/IcM_Troubleshooting.svg;`
- **Size:** 68x68

### Image Definition

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Image_Definition.svg;`
- **Size:** 68x64

### Image Version

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Image_Version.svg;`
- **Size:** 68x68

### Internet Analyzer Profiles

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Internet_Analyzer_Profiles.svg;`
- **Size:** 68x64

### Kubernetes Fleet Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Kubernetes_Fleet_Manager.svg;`
- **Size:** 68x68

### Log Analytics Query Pack

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Log_Analytics_Query_Pack.svg;`
- **Size:** 68x68

### Managed DevOps Pools

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Managed_DevOps_Pools.svg;`
- **Size:** 68x68

### Managed File Shares

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Managed_File_Shares.svg;`
- **Size:** 68x68

### Managed Instance Apache Cassandra

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Managed_Instance_Apache_Cassandra.svg;`
- **Size:** 68x68

### MedTech Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/MedTech_Service.svg;`
- **Size:** 68x61

### Mission Landing Zone

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Mission_Landing_Zone.svg;`
- **Size:** 68x64

### Modular Data Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Modular_Data_Center.svg;`
- **Size:** 68x68

### Monitor Dashboard

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Monitor_Dashboard.svg;`
- **Size:** 68x63

### Monitor Health Models

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Monitor_Health_Models.svg;`
- **Size:** 68x68

### Monitor Pipeline

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Monitor_Pipeline.svg;`
- **Size:** 68x49

### MS Dev Box

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/MS_Dev_Box.svg;`
- **Size:** 68x68

### Network Function Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Network_Function_Manager.svg;`
- **Size:** 60x68

### Network Function Manager Functions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Network_Function_Manager_Functions.svg;`
- **Size:** 68x62

### Network Manager

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Network_Manager.svg;`
- **Size:** 64x68

### Network Security Perimeters

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Network_Security_Perimeters.svg;`
- **Size:** 68x68

### Open Supply Chain Platform

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Open_Supply_Chain_Platform.svg;`
- **Size:** 68x68

### Orbital

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Orbital.svg;`
- **Size:** 68x68

### OSConfig

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/OSConfig.svg;`
- **Size:** 68x57

### Peering Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Peering_Service.svg;`
- **Size:** 68x69

### Peerings

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Peerings.svg;`
- **Size:** 68x58

### Private Endpoints

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Private_Endpoints.svg;`
- **Size:** 68x65

### Private Mobile Network

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Private_Mobile_Network.svg;`
- **Size:** 68x48

### Quotas

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Quotas.svg;`
- **Size:** 68x48

### Reserved Capacity

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Reserved_Capacity.svg;`
- **Size:** 58x68

### Reserved Capacity Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Reserved_Capacity_Groups.svg;`
- **Size:** 58x68

### Resource Guard

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Resource_Guard.svg;`
- **Size:** 57x68

### Resource Mover

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Resource_Mover.svg;`
- **Size:** 56x68

### RTOS

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/RTOS.svg;`
- **Size:** 68x68

### Savings Plan

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Savings_Plan.svg;`
- **Size:** 68x68

### SCVMM Management Servers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/SCVMM_Management_Servers.svg;`
- **Size:** 68x68

### Sonic Dash

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Sonic_Dash.svg;`
- **Size:** 62x68

### Sphere

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Sphere.svg;`
- **Size:** 66x68

### SSH Keys

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/SSH_Keys.svg;`
- **Size:** 68x60

### Storage Actions

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Storage_Actions.svg;`
- **Size:** 68x68

### Storage Mover

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Storage_Mover.svg;`
- **Size:** 68x67

### Storage Tasks

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Storage_Tasks.svg;`
- **Size:** 68x68

### Support Center Blue

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Support_Center_Blue.svg;`
- **Size:** 60x68

### Support Sustainability

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Sustainability.svg;`
- **Size:** 68x68

### Targets Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Targets_Management.svg;`
- **Size:** 68x68

### Template Specs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Template_Specs.svg;`
- **Size:** 57x68

### Test Base

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Test_Base.svg;`
- **Size:** 68x48

### Update Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Update_Center.svg;`
- **Size:** 68x68

### Video Analyzers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Video_Analyzers.svg;`
- **Size:** 68x48

### Video Indexer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Azure_Video_Indexer.svg;`
- **Size:** 60x68

### Virtual Enclaves

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Virtual_Enclaves.svg;`
- **Size:** 60x68

### Virtual Instance for SAP

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Virtual_Instance_for_SAP.svg;`
- **Size:** 68x63

### VM Application Definition

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/VM_Application_Definition.svg;`
- **Size:** 68x63

### VM Application Version

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/VM_Application_Version.svg;`
- **Size:** 68x68

### WAC

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/WAC.svg;`
- **Size:** 62x68

### WAC Installer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/WAC_Installer.svg;`
- **Size:** 68x68

### Web App Database

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Web_App_Database.svg;`
- **Size:** 68x68

### Web Jobs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Web_Jobs.svg;`
- **Size:** 66x68

### Windows Notification Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Windows_Notification_Services.svg;`
- **Size:** 68x68

### Windows Virtual Desktop

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Windows_Virtual_Desktop.svg;`
- **Size:** 68x68

### Worker Container App

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Worker_Container_App.svg;`
- **Size:** 68x66

### Workspace Gateway

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/other/Workspace_Gateway.svg;`
- **Size:** 68x57

### AAD Licenses

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/AAD_Licenses.svg;`
- **Size:** 65x68

### Entra Connect Health

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Active_Directory_Connect_Health2.svg;`
- **Size:** 68x60

### VMWare Solution

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/azure_vmware_solution/AVS.svg;`
- **Size:** 68x54

## Power Platform

### AI Builder

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/AIBuilder.svg;`
- **Size:** 68x68

### Copilot Studio

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/CopilotStudio.svg;`
- **Size:** 68x62

### Dataverse

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/Dataverse.svg;`
- **Size:** 68x52

### PowerApps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/PowerApps.svg;`
- **Size:** 68x65

### PowerAutomate

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/PowerAutomate.svg;`
- **Size:** 68x54

### PowerBI

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/PowerBI.svg;`
- **Size:** 51x68

### PowerFx

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/PowerFx.svg;`
- **Size:** 68x65

### PowerPages

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/PowerPages.svg;`
- **Size:** 68x68

### PowerPlatform

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/power_platform/PowerPlatform.svg;`
- **Size:** 64x68

## Preview

### IoT Edge

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/preview/IoT_Edge.svg;`
- **Size:** 68x67

### Time Series Data Sets

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/preview/Time_Series_Data_Sets.svg;`
- **Size:** 48x64

### Web Environment

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/preview/Web_Environment.svg;`
- **Size:** 64x66

## Security

### AD Risky Signins

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Azure_AD_Risky_Signins.svg;`
- **Size:** 68x68

### AD Risky Users

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Azure_AD_Risky_Users.svg;`
- **Size:** 68x68

### Application Security Groups

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Application_Security_Groups.svg;`
- **Size:** 56x68

### Conditional Access

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Conditional_Access.svg;`
- **Size:** 56x68

### Defender

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Azure_Defender.svg;`
- **Size:** 56x68

### Extended Security Updates

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/ExtendedSecurityUpdates.svg;`
- **Size:** 64x70

### Identity Secure Score

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Identity_Secure_Score.svg;`
- **Size:** 62x68

### Key Vaults

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Key_Vaults.svg;`
- **Size:** 68x68

### MS Defender EASM

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/MS_Defender_EASM.svg;`
- **Size:** 55x68

### Multifactor Authentication

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Multifactor_Authentication.svg;`
- **Size:** 55x68

### Security Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Security_Center.svg;`
- **Size:** 56x68

### Sentinel

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/security/Azure_Sentinel.svg;`
- **Size:** 56x68

### AD Authentication Methods

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/Managed_Identities.svg;`
- **Size:** 68x66

### AD Privileged Identity Management

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/identity/PIM.svg;`
- **Size:** 60x68

## Storage

### Data Lake Storage Gen1

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Data_Lake_Storage_Gen1.svg;`
- **Size:** 64x52

### Data Share Invitations

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Data_Share_Invitations.svg;`
- **Size:** 68x45

### Data Shares

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Data_Shares.svg;`
- **Size:** 64x55

### Fileshare

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Azure_Fileshare.svg;`
- **Size:** 68x68

### HCP Cache

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Azure_HCP_Cache.svg;`
- **Size:** 68x63

### Import Export Jobs

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Import_Export_Jobs.svg;`
- **Size:** 64x67

### NetApp Files

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Azure_NetApp_Files.svg;`
- **Size:** 65x52

### Stack Edge

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Azure_Stack_Edge.svg;`
- **Size:** 68x48

### Storage Accounts

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Storage_Accounts.svg;`
- **Size:** 65x52

### Storage Accounts (Classic)

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Storage_Accounts_Classic.svg;`
- **Size:** 65x52

### Storage Explorer

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Storage_Explorer.svg;`
- **Size:** 58x68

### Storage Sync Services

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/Storage_Sync_Services.svg;`
- **Size:** 72x60

### StorSimple Data Managers

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/storage/StorSimple_Data_Managers.svg;`
- **Size:** 48x64

## Web

### API Center

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/web/API_Center.svg;`
- **Size:** 68x68

### App Space

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/web/App_Space.svg;`
- **Size:** 68x68

### Media Service

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/web/Azure_Media_Service.svg;`
- **Size:** 68x68

### Notification Hub Namespaces

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/web/Notification_Hub_Namespaces.svg;`
- **Size:** 67x56

### SignalR

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/web/SignalR.svg;`
- **Size:** 68x68

### App Service Certificates

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/app_services/App_Service_Certificates.svg;`
- **Size:** 68x62

### Front Door and CDN Profiles

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/networking/Front_Doors.svg;`
- **Size:** 68x60

### Spring Apps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/compute/Azure_Spring_Cloud.svg;`
- **Size:** 68x68

### Static Apps

- **Style:** `aspect=fixed;html=1;shape=image;points=[];align=center;image;fontSize=12;image=img/lib/azure2/preview/Static_Apps.svg;`
- **Size:** 68x54
