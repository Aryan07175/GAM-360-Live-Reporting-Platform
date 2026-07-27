# Phase 4 — Enterprise Creative Intelligence

## Overview
Phase 4 expands Ask GAM 360 into Creative Operations, enabling AdOps engineers, creative designers, and account executives to inspect, audit, and analyze Google Ad Manager creative assets and templates in real time.

## Capabilities

### 1. Creative Asset Discovery (`getCreatives`)
- **Query Engine**: Connects to GAM API `CreativeService` via PQL statement building.
- **Support Filters**:
  - `name_filter`: Partial match on creative names.
  - `advertiser_id`: Filter creatives belonging to a specific advertiser.
  - `type_filter`: Match creative subclass format (e.g., `ImageCreative`, `Html5Creative`, `VideoCreative`, `NativeCreative`, `AdExchangeCreative`, `AdSenseCreative`, `VastRedirectCreative`, `CustomCreative`).
  - `size_filter`: Match specific creative dimensions (e.g., `300x250`, `728x90`, `1920x1080`).
- **Returned Metadata**:
  - `creative_id` & `name`
  - `advertiser_id`
  - `creative_type` (resolved subclass name)
  - `size` (formatted as Width x Height or aspect ratio)
  - `preview_url` (direct ad server preview link)
  - `snippet_preview` (sanitized snippet code or third-party URL snippet)
  - `is_native_eligible` & `is_interstitial` flags

### 2. Creative Template Management (`getCreativeTemplates`)
- **Query Engine**: Connects to GAM API `CreativeTemplateService`.
- **Support Filters**:
  - `name_filter`: Filter templates by name.
  - `type_filter`: Match template origin (`SYSTEM` vs. `CUSTOM`).
  - `status_filter`: Match template lifecycle status (`ACTIVE`, `INACTIVE`, `ARCHIVED`).
- **Returned Metadata**:
  - `template_id` & `name`
  - `type` & `status`
  - `description`
  - `variables` (names, types, and default values of custom variables)
  - `is_native_eligible` & `is_interstitial` flags

### 3. Creative Inventory Diagnostics (`getCreativeDiagnostics`)
- **Analytics Engine**: Aggregates and audits live creative assets across network advertisers.
- **Diagnostic Insights**:
  - **Type Distribution**: Breakdown of creative formats (e.g., Programmatic Backfill vs. Video VAST vs. HTML5 Rich Media vs. Standard Image).
  - **Size Distribution**: Top ad sizes across active creatives.
  - **Health Checks**: Identifies creatives with missing preview URLs, unsupported formats, or policy/badging exceptions.
  - **Format Capabilities**: Quantifies native-eligible and interstitial-ready creatives in the network.

### 4. Live Creative Performance Reporting
- Seamlessly integrates with Ask GAM 360's live reporting engine (`runReportJob`).
- By requesting `extra_dims=['CREATIVE_NAME']` or `extra_dims=['CREATIVE_ID']`, the engine automatically transitions to entity-level reporting, mapping line-item level impressions, clicks, CTR, eCPM, and revenue directly to individual creatives.

## Target Users
- **Creative Team**: Rapidly verify snippet rendering, custom template variables, and preview links.
- **AdOps & Campaign Managers**: Audit creative sizes, troubleshoot non-delivering creatives, and analyze creative type distributions.
