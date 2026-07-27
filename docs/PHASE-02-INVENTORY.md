# Phase 2 — Enterprise Inventory Intelligence

## Priority: Highest
**Status:** In Progress

## Purpose
Enable Ask GAM 360 to understand and query Google Ad Manager inventory structures, hierarchies, placements, sizes, and targeting configurations using live API data without fabricating metrics or entities.

## Core Capabilities
1. **Ad Unit Hierarchy & Diagnostics (`InventoryService`)**:
   - Live query of Ad Units by name, ID, or ad unit code.
   - Hierarchy resolution (parent/child relationships, path tracking).
   - Size mapping and target window analysis.
   - Status filtering (ACTIVE, INACTIVE, ARCHIVED).

2. **Placements & Ad Unit Mapping (`PlacementService`)**:
   - Retrieve active placements across the network.
   - Resolve associated ad unit IDs targeted by placements.
   - Placement descriptions and status analysis.

3. **Key-Value Targeting (`CustomTargetingService`)**:
   - Query Custom Targeting Keys (PREDEFINED vs. FREEFORM).
   - Resolve Custom Targeting Values for specific targeting keys.
   - Audit reportable types (CUSTOM_DIMENSION vs. OFF).

4. **Inventory Fill & Unfilled Analysis**:
   - Combine inventory structural data with Phase 1 live reporting metrics.
   - Diagnose unfilled impressions and unmatched ad requests across specific ad units and placements.

## Supported Questions & AI Use Cases
- *"Show me all active ad units matching 'Mobile' or 'App'."*
- *"What are the ad unit sizes configured for top-level ad unit X?"*
- *"List all active placements and the ad units they contain."*
- *"What custom targeting keys are defined as custom dimensions in our network?"*
- *"Which ad units have the lowest fill rate over the past 7 days?"*

## Architecture & Integration
```
[Ask GAM 360 AI / Dashboard]
        │
        ▼ (MCP / Bedrock Tool Calls: getAdUnitHierarchy, getPlacements, getCustomTargeting)
[MCP Server Orchestrator (server.py)]
        │
        ▼ (GAMClient SOAP Calls)
[Google Ad Manager SOAP API v202602]
        ├── InventoryService.getAdUnitsByStatement
        ├── PlacementService.getPlacementsByStatement
        └── CustomTargetingService.getCustomTargetingKeysByStatement
```
