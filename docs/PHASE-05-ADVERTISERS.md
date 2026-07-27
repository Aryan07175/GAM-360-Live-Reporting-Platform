# Phase 5 — Advertiser & Commercial Intelligence

## Overview
Phase 5 expands Ask GAM 360 into Commercial & Account Operations, enabling sales executives, account managers, and finance teams to query, audit, and analyze Google Ad Manager customer accounts (advertisers, agencies, programmatic buyers, and child publishers) in real time.

## Capabilities

### 1. Customer & Company Discovery (`getCompanies`)
- **Query Engine**: Connects to GAM API `CompanyService` via PQL statement building.
- **Supported Filters**:
  - `name_filter`: Partial match on customer/company names.
  - `type_filter`: Match company classification (e.g., `ADVERTISER`, `AGENCY`, `AD_NETWORK`, `CHILD_PUBLISHER`, `HOUSE_ADVERTISER`, `HOUSE_AGENCY`).
  - `credit_status_filter`: Match commercial credit standing (`ACTIVE`, `INACTIVE`, `BLOCKED`, `ON_HOLD`).
- **Returned Metadata**:
  - `company_id` & `name`
  - `company_type`
  - `credit_status`
  - `email` & `primary_phone`
  - `external_id` (CRM / ERP integration ID)
  - `primary_contact_id`
  - `comment`

### 2. Commercial Contact Directory (`getContacts`)
- **Query Engine**: Connects to GAM API `ContactService`.
- **Supported Filters**:
  - `name_filter`: Search contact names or emails.
  - `company_id`: Filter contacts belonging to a specific advertiser or agency.
- **Returned Metadata**:
  - `contact_id` & `name`
  - `email` & `title`
  - `work_phone` & `cell_phone`
  - `company_id` & `status` (`ACTIVE`, `UNVERIFIED`, `INACTIVE`)

### 3. Commercial Portfolio Analytics (`getAdvertiserAnalytics`)
- **Analytics Engine**: Audits network customer health across active companies.
- **Diagnostic Insights**:
  - **Credit Risk Breakdown**: Quantifies active customers vs. accounts on credit hold or blocked.
  - **Portfolio Segmentation**: Categorizes customers by company type (Direct Advertisers vs. Agencies vs. Ad Networks vs. MCM Child Publishers).
  - **Account Coverage**: Checks for missing primary contacts or external CRM billing references.

### 4. Revenue & Order Rankings by Advertiser (`getAdvertiserRankings`)
- **Reporting Engine**: Directly interfaces with Ask GAM 360's live reporting pipeline (`runReportJob` with dimension `ADVERTISER_NAME`).
- **Commercial Metrics**:
  - Ranks top advertisers across customizable time horizons by total revenue (`revenue`) or impression volume (`impressions`).
  - Calculates share of total network revenue (%) per customer.
  - Computes customer-specific effective CPM (`eCPM`) and click-through rates (`CTR`).

## Target Users
- **Sales Executives**: Quickly identify top-spending advertisers, historical spend trends, and agency partners.
- **Account Managers**: Audit customer credit holds, verify primary contact details, and check active campaigns per customer.
- **Finance Teams**: Monitor accounts receivable credit statuses and reconcile CRM external IDs against ad server records.
