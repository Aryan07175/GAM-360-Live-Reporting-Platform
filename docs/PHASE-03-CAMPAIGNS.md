# Phase 3 — Enterprise Campaign & Delivery Intelligence

## Priority: Highest
**Status:** In Progress

## Purpose
Enable Ask GAM 360 to monitor and diagnose campaign delivery, orders, line item configurations, priority tiers, budget pacing, and flight schedules using live Google Ad Manager SOAP API data.

## Core Capabilities
1. **Orders & Campaign Management (`OrderService`)**:
   - Query Orders by name, status (APPROVED, DRAFT, PAUSED, CANCELED, COMPLETED), or advertiser ID.
   - Retrieve total campaign budget, currency code, start/end dates, and aggregate delivery metrics.

2. **Line Item Configurations & Priority Tiers (`LineItemService`)**:
   - Query Line Items by order ID, status (DELIVERING, PAUSED, READY, COMPLETED), or type.
   - Support all GAM priority tiers and line item types:
     - **Sponsorship** (CPD/CPM, high priority share-of-voice)
     - **Standard** (contracted impression goals)
     - **Network / Bulk** (remaining impressions / volume deals)
     - **Price Priority** (unreserved inventory competing on rate)
     - **House / Ad Exchange** (remnant / programmatic backfill)
   - Inspect rates (eCPM, CPM, CPC, CPD), cost types, and contracted units bought.

3. **Delivery Progress & Pacing Diagnostics**:
   - Real-time calculation of delivery progress against flight duration.
   - **Flight Elapsed %**: `(current_date - start_date) / (end_date - start_date) * 100`
   - **Delivery %**: `(units_delivered / contracted_units_bought) * 100`
   - **Pacing Index**: Calculate whether a line item is **On Track**, **Under Pacing (< 90% expected)**, or **Over Pacing (> 110% expected)**.
   - Audit video completions, viewable impressions, and click-through delivery stats.

## Supported Questions & AI Use Cases
- *"List all active campaigns and orders currently delivering for advertiser X."*
- *"Show me all Sponsorship and Standard line items that are DELIVERING."*
- *"Which line items are currently under-pacing or at risk of not meeting their contracted goals?"*
- *"What is the delivery progress and budget spent for Order ID 12345?"*
- *"List all House or Price Priority line items configured in our network."*

## Architecture & Integration
```
[Ask GAM 360 AI / Dashboard]
        │
        ▼ (MCP / Bedrock Tool Calls: getOrders, getLineItems, getDeliveryProgress)
[MCP Server Orchestrator (server.py)]
        │
        ▼ (GAMClient SOAP Calls)
[Google Ad Manager SOAP API v202602]
        ├── OrderService.getOrdersByStatement
        └── LineItemService.getLineItemsByStatement
```
