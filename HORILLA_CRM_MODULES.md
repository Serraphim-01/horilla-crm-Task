# Horilla CRM Modules -- Overview with Examples

All examples use **Acme Software Solutions**, a B2B SaaS company selling a project management tool ($3,000/yr per 10-seat tier).

---

## 1. Accounts

Accounts represent the **companies/organizations** you do business with. Each account has a detailed profile: industry, revenue, employee count, billing/shipping addresses, account type, and ownership. Accounts can have a parent-child hierarchy (e.g., a global HQ with regional subsidiaries).

**Example**: Acme sells to *Pixelcraft Design* (50 employees, London). An **Account** record stores:

| Field | Value |
|-------|-------|
| Name | Pixelcraft Design |
| Account Owner | Sarah (AE) |
| Type | Customer Direct |
| Industry | Technology |
| Annual Revenue | $5,000,000 |
| Employees | 50 |
| Billing City | London |
| Website | https://pixelcraft.io |
| Rating | Warm |
| Parent Account | *(none — top-level)* |

Multiple **Contacts** and **Opportunities** are linked to this Account.

```python
# Account fields
name, account_owner, account_type, industry, annual_revenue
number_of_employees, website, phone, parent_account
billing_city, billing_state, billing_zip, billing_country
shipping_city, shipping_state, shipping_zip
rating, description, account_score
```

---

## 2. Contacts

Contacts are the **individual people** within an Account. Each contact has a name, email, phone, job role, and optional relationship to an Account (via `ContactAccountRelationship` with a role like "Decision Maker" or "Champion"). Contacts can also be standalone (not tied to an Account).

**Example**: At *Pixelcraft Design*, Sarah deals with three Contacts:

| Field | Jane Smith | Tom Lee | Priya Kapoor |
|-------|-----------|---------|-------------|
| First Name | Jane | Tom | Priya |
| Last Name | Smith | Lee | Kapoor |
| Email | jane@pixelcraft.io | tom@pixelcraft.io | priya@pixelcraft.io |
| Phone | +44 20 7123 4567 | +44 20 7123 8910 | +44 20 7123 1112 |
| Account | Pixelcraft Design | Pixelcraft Design | Pixelcraft Design |
| Role | Decision Maker | Technical Evaluator | Procurement |
| Is Primary | Yes | No | No |
| Contact Owner | Sarah (AE) | Sarah (AE) | Sarah (AE) |
| Source | Web | Referral | Web |

The **Opportunity** "Pixelcraft - PM Tool License" has each contact assigned via `OpportunityContactRole`, with Jane marked as the primary contact.

```python
# Contact fields
first_name, last_name, email, phone, secondary_phone
contact_owner, title, department, account (via ContactAccountRelationship)
is_primary, contact_source, description, birth_date
address_city, address_state, address_zip, address_country
parent_contact, languages, assistant, contact_score
```

---

## 3. Leads

Leads are **unqualified prospects** — people who have shown interest but haven't been vetted yet. Each Lead goes through a **Lead Status** pipeline (configurable stages like New → Contacted → Qualified → Disqualified → Converted). Leads have a source (website, referral, campaign, etc.) and an auto-calculated **lead score** based on scoring rules. When qualified, a Lead can be **converted** into an Account + Contact + Opportunity.

**Example**: Jane Smith fills out a "Request Demo" form on Acme's website.

| Field | Value |
|-------|-------|
| First Name | Jane |
| Last Name | Smith |
| Email | jane@pixelcraft.io |
| Company | Pixelcraft Design |
| Lead Source | Website |
| Lead Status | *New* |
| Lead Owner | Sarah (SDR) |
| Requirements | "Need a 50-seat PM tool for our remote team" |
| Lead Score | 30 *(scoring: website source +10, company size >20 +20)* |
| Industry | Technology |

**Pipeline flow**:
```
New (0%) → Contacted (10%) → Qualified (50%) → Converted (100%)
                                              → Disqualified (0%)
```

Sarah calls Jane, discusses requirements, and moves the Lead to *Qualified*. She then clicks "Convert" — this creates:
- **Account**: Pixelcraft Design
- **Contact**: Jane Smith (linked to Account)
- **Opportunity**: Pixelcraft - PM Tool License

The Lead's `is_convert` flag is set to `True`.

```python
# Lead fields
first_name, last_name, email, company, contact_number
lead_source, lead_status (FK -> LeadStatus with probability)
lead_owner, requirements, industry, annual_revenue
lead_score, is_convert, city, state, country, zip_code
```

---

## 4. Opportunities

Opportunities represent **active deals** in your sales pipeline. Each opportunity moves through **Opportunity Stages** (e.g., Qualification → Discovery → Proposal → Negotiation → Closed Won/Lost). Key metrics:

- **Amount**: the deal value
- **Probability**: % chance of closing (auto-set from stage, but overridable)
- **Expected Revenue**: `amount * probability / 100` (auto-calculated)
- **Forecast Category**: auto-set from probability ranges (pipeline / best_case / commit / closed)
- **Stage Type**: open / won / lost

**Example**: After converting Jane's Lead, Sarah has this Opportunity:

| Field | Value |
|-------|-------|
| Name | Pixelcraft Design - PM Tool License |
| Account | Pixelcraft Design |
| Amount | $15,000 |
| Probability | 60% |
| Expected Revenue | $9,000 |
| Stage | *Negotiation* |
| Stage Type | Open |
| Close Date | June 30, 2026 |
| Owner | Sarah (AE) |
| Forecast Category | *best_case* (auto from 41-70% probability) |
| Opportunity Type | New Customer |
| Lead Source | Website |
| Primary Campaign Source | Google Ads Q2 |
| Next Step | "Send revised pricing to CFO" |
| Description | "50-seat annual license, with 20% uplift for premium support" |

**Stage progression**:
```
Qualification (10%) → Discovery (25%) → Proposal (50%) → Negotiation (75%) → Closed Won (100%)
                                                                          → Closed Lost (0%)
```

When Sarah moves it to *Closed Won* ($15,000):
- `forecast_category` → *closed*
- The Campaign "Google Ads Q2" auto-updates: `won_opportunities_in_campaign` += 1, `value_won_opportunities` += $15,000
- The revenue is counted in Forecast as closed revenue

```python
# Opportunity fields
name, amount, probability, expected_revenue, close_date
stage (FK -> OpportunityStage with name/order/probability/stage_type)
owner, account (FK -> Account), primary_campaign_source (FK -> Campaign)
forecast_category, opportunity_type, delivery_installation_status
description, next_step, main_competitors, lead_source
quantity, order_number, tracking_number
```

---

## 5. Campaigns

Campaigns track **marketing initiatives** and measure their ROI. They have a type (email, event, social media, webinar, referral, advertisement), status (planned → in progress → completed/aborted), budget tracking, and denormalized counters for leads generated, opportunities created, and revenue won.

Campaign **members** (leads or contacts) are tracked through `CampaignMember` with statuses: planned → sent → received → responded.

**Example**: Acme runs *Google Ads Q2 2026*:

| Field | Value |
|-------|-------|
| Campaign Name | Google Ads Q2 2026 |
| Type | Advertisement |
| Status | *In Progress* |
| Owner | Marketing Team |
| Start Date | April 1, 2026 |
| End Date | June 30, 2026 |
| Budget Cost | $5,000 |
| Actual Cost | $4,200 |
| Number Sent | 10,000 (ad impressions) |
| Expected Response | 3% |
| Parent Campaign | *(none)* |

**Auto-tracked results after sync**:

| Metric | Value |
|--------|-------|
| Leads in Campaign | 320 |
| Converted Leads | 45 |
| Contacts in Campaign | 120 |
| Opportunities in Campaign | 28 |
| Won Opportunities | 6 |
| Value of Opportunities | $420,000 |
| Value of Won Opportunities | $180,000 |
| Responses | 412 |

**ROI**: ($180,000 - $4,200) / $4,200 = **4,185%**

This campaign is linked to Jane's Lead (`Lead.primary_campaign_source` = this Campaign), which means when her Lead converts to an Opportunity, the Campaign auto-records it.

```python
# Campaign fields
campaign_name, campaign_owner, campaign_type, status
start_date, end_date, expected_revenue, budget_cost, actual_cost
number_sent, expected_response, description
parent_campaign (self-referential FK for sub-campaigns)

# Auto-tracked counters
leads_in_campaign, converted_leads_in_campaign
contacts_in_campaign, opportunities_in_campaign
won_opportunities_in_campaign, value_opportunities
value_won_opportunities, responses_in_campaign
```

---

## 6. Forecast

Forecasts predict **future revenue** based on the opportunity pipeline. A Forecast is created for a specific period/quarter/fiscal year using a **ForecastType** (deal revenue amount, expected revenue, or deal quantity). It aggregates all open opportunities by their `forecast_category`:

| Category | Probability | Meaning |
|----------|-------------|---------|
| Pipeline | < 10% | Early-stage, uncertain |
| Best Case | 10-70% | Likely but not committed |
| Commit | 71-99% | High confidence |
| Closed | 100% | Won |
| Omitted | — | Excluded from forecast |

Forecasts go through an approval workflow: Draft → Submitted → Approved/Rejected.

**Example**: VP of Sales reviews **Q3 2026 Forecast**:

```
Forecast:   Q3 2026 - Revenue Forecast
Type:       Deal Revenue (Amount)
Fiscal Year: FY2026
Owner:      VP of Sales
Status:     Draft
Target:     $2,000,000
─────────────────────────────────────
Pipeline (≤10%):       $800,000   6 early deals
Best Case (11-70%):    $950,000   4 mid-stage deals  ← Pixelcraft ($15k) is here
Commit (71-99%):       $450,000   3 late-stage deals
Closed (100%):         $200,000   2 deals won in Q3
─────────────────────────────────────
Total in pipeline:   $2,400,000
Gap to target:      -$400,000     (need 2 more commit-level deals)

Achievement:          10%  ($200k closed / $2M target)
```

**When Pixelcraft moves to Commit (85%)**:
- `best_case_amount` drops by $15,000
- `commit_amount` increases by $15,000
- Rep's individual `ForecastTarget` achievement updates

The VP submits it (*Draft → Submitted*), CFO approves (*Approved*), board sees the report.

**Per-rep targets** via `ForecastTarget`:

| Rep | Target | Current | Achievement |
|-----|--------|---------|-------------|
| Sarah | $500,000 | $380,000 | 76% |
| Mike | $750,000 | $510,000 | 68% |
| Anna | $750,000 | $620,000 | 83% |

```python
# Forecast fields
name, forecast_type (FK -> ForecastType), owner
period, quarter, fiscal_year
status (draft/submitted/approved/rejected)
target_amount, pipeline_amount, best_case_amount
commit_amount, closed_amount, actual_amount
target_quantity, pipeline_quantity, best_case_quantity
commit_quantity, closed_quantity, actual_quantity
notes, submitted_at, approved_at, approved_by

# Computed properties
achievement_percentage, performance_percentage
gap_amount, gap_percentage, closed_percentage
```

---

## 7. Reports

Reports let you build **custom analytics** against any module. A `Report` stores:
- **Module**: which model to report on (Leads, Opportunities, Accounts, etc. via ContentType)
- **Chart Type**: column, line, pie, bar, funnel, donut, stacked, scatter, treemap, area, heatmap, sankey, radar
- **Selected Columns**: which fields to display in the table
- **Row Groups / Column Groups**: for pivot/crosstab aggregations
- **Aggregate Columns**: field + aggregation function (sum, count, avg, min, max)
- **Filters**: JSON-stored filter criteria
- **Chart Field / Chart Value Field**: X-axis and Y-axis fields

Reports can be saved in folders and shared with other users.

**Example 1**: "Q2 Opportunity Funnel" (Funnel chart)

| Setting | Value |
|---------|-------|
| Module | Opportunities |
| Chart Type | Funnel |
| X-Axis (chart_field) | stage |
| Value (chart_value_field) | amount |
| Aggregate Function | SUM |
| Filters | close_date between Apr 1 - Jun 30 |

```
           Qualification:  $2,100,000
          Discovery:       $1,500,000
          Proposal:        $980,000
          Negotiation:     $520,000
          Closed Won:      $200,000
```

**Example 2**: "Rep Performance" (Bar chart)

| Setting | Value |
|---------|-------|
| Module | Opportunities |
| Chart Type | Bar |
| X-Axis | owner (group by rep) |
| Value | amount (SUM) |
| Filters | stage_type = won, close_date in Q3 |
| Row Groups | owner |
| Column Groups | stage |

Shows bars for each rep's won revenue by stage:

```
Rep      | Qualif. | Discov. | Propos. | Negot. | Won    | Total
Sarah    | $0      | $0      | $0      | $15k   | $85k   | $100k
Mike     | $10k    | $25k    | $0      | $0     | $50k   | $85k
Anna     | $0      | $0      | $30k    | $20k   | $65k   | $115k
```

**Example 3**: "Campaign ROI" (Table report with aggregates)

| Setting | Value |
|---------|-------|
| Module | Campaigns |
| Columns | campaign_name, campaign_type, budget_cost, actual_cost, value_won_opportunities |
| Aggregate | SUM on actual_cost, SUM on value_won_opportunities |
| Chart | None (table only) |
| Filter | status = completed |

```
Campaign              Type      Budget   Actual   Won Revenue   ROI
Google Ads Q2         Ads       $5,000   $4,200   $180,000      4,185%
Summer Webinar        Webinar   $2,000   $1,800   $95,000       5,178%
Partner Referral      Referral  $500     $300     $45,000      14,900%
```

```python
# Report fields
name, report_owner, module (FK -> ContentType)
chart_type, chart_field, chart_value_field, chart_field_stacked
selected_columns, row_groups, column_groups
aggregate_columns, filters
folder (FK -> ReportFolder with hierarchy)
is_favourite, shared_with (M2M -> User)
```

---

## 8. Dashboards

Dashboards provide **at-a-glance visualization** via configurable widgets. Each dashboard contains multiple widgets, each of which can be a chart (using the same chart engine as Reports), a KPI metric, or a list view. Widgets are drag-and-drop reorderable, have date range filtering, and can be set as default.

**Example**: Sarah's "Daily Sales Dashboard"

```
┌─────────────────────────────────────────────────────────────────┐
│  🎯 My Pipeline ($1.2M)            │  📊 Q3 Achievement: 68%   │
│  ━━━━━━━━━━━━━━━━━━━━              │  ━━━━━━━━━━━━━━━━━━━━     │
│  • Open deals: 12                   │  Target:    $1.2M         │
│  • Commit deals: 3 ($450k)          │  Achieved:  $816k         │
│  • Best case: 4 ($950k)             │  Remaining: $384k / 45d   │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  📈 Won Revenue by Month (Line Chart)                           │
│                                                                  │
│  $200k ┤        ╱╲                                               │
│  $150k ┤      ╱  ╲    ╱╲                                         │
│  $100k ┤    ╱    ╲  ╱  ╲   ╱╲                                    │
│   $50k ┤  ╱      ╲╱    ╲ ╱  ╲                                   │
│     0  └──────────────────────────────                           │
│         Jan  Feb  Mar  Apr  May  Jun                             │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  🔥 Deals Closing This Week (Table)                             │
│                                                                  │
│  Deal                    | Amount | Stage      | Owner           │
│  ─────────────────────────────────────────────────────────────── │
│  Pixelcraft - PM Tool   | $15k   | Negot.     | Sarah           │
│  Nova Corp - Enterprise | $45k   | Closed Won | Sarah           │
│  Bluebird - 3yr Renewal | $28k   | Closing    | Mike            │
└─────────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│  📉 Pipeline by Stage (Funnel Chart)                             │
│                                                                  │
│         Qualification                          $2.1M             │
│           Discovery                            $1.5M             │
│            Proposal                            $980K             │
│           Negotiation                          $520K             │
│           Closed Won                           $200K             │
│         ╔══════════════════════════╗                            │
│         ║ CONVERSION: 9.5%        ║                            │
│         ╚══════════════════════════╝                            │
└─────────────────────────────────────────────────────────────────┘
```

```python
# Dashboard (via horilla_dashboard app) — not a single model but a system
# of configurable Widget instances per user
Widget fields:
  title, widget_type (chart/kpi/list)
  report (FK -> Report)  # Reuses Report's chart config
  dashboard (FK -> Dashboard)
  date_range, order, is_default
```

---

## 9. Roles & Role Types

Horilla CRM defines four distinct role types, each serving a different purpose. All are stored in `horilla_core/models/organization.py`.

### 9a. Role

The general organizational **Role** governs system-wide user permissions. Each user is assigned one via `HorillaUser.role`.

| Field | Type | Description |
|-------|------|-------------|
| `role_name` | `CharField` | Name (e.g., "Sales Manager", "Admin") |
| `parent_role` | `FK(self)` | Hierarchical parent (for subroles) |
| `permissions` | `M2M(Permission)` | Django permissions attached to the role |

**Used in CRM**: `ForecastTarget.role` — determines org hierarchy for forecast targets.

### 9b. Team Role

**TeamRole** defines a user's function on a specific **opportunity team** (no system permissions — just a label).

| Field | Type | Description |
|-------|------|-------------|
| `team_role_name` | `CharField` | Name (e.g., "Sales Engineer", "Account Manager") |
| `description` | `TextField` | Optional description |

**Used in CRM**: `OpportunityTeamMember.team_role` — what role this user plays on this deal. Also `DefaultOpportunityMember.team_role` for auto-assignment defaults.

### 9c. Customer Role

**CustomerRole** defines what function a **contact** plays for an account or opportunity (e.g., "Decision Maker", "Champion", "End User").

| Field | Type | Description |
|-------|------|-------------|
| `customer_role_name` | `CharField` | Name (e.g., "Decision Maker", "Technical Evaluator") |
| `description` | `TextField` | Optional description |

**Used in CRM**: `ContactAccountRelationship.role` — the contact's role in the account. Also `OpportunityContactRole.role` — the contact's role on a specific opportunity.

### 9d. Partner Role

**PartnerRole** defines the type of **partner relationship** between two accounts (e.g., "Reseller", "Technology Partner").

| Field | Type | Description |
|-------|------|-------------|
| `partner_role_name` | `CharField` | Name (e.g., "Reseller", "Installation Partner") |
| `description` | `TextField` | Optional description |

**Used in CRM**: `PartnerAccountRelationship.role` — what type of partnership two accounts have.

### Summary

| Role | Scope | Linked From | Example Values |
|------|-------|-------------|----------------|
| **Role** | System-wide user permissions | `HorillaUser.role`, `ForecastTarget.role` | Sales Manager, Admin |
| **Team Role** | User's function on an opportunity team | `OpportunityTeamMember.team_role` | Sales Engineer, Account Manager |
| **Customer Role** | Contact's function for an account/opportunity | `ContactAccountRelationship.role`, `OpportunityContactRole.role` | Decision Maker, Champion |
| **Partner Role** | Relationship type between two accounts | `PartnerAccountRelationship.role` | Reseller, Technology Partner |

---

## 10. Scoring Rules

Defined in `horilla_crm/leads/models.py`. A **3-tier rules engine** that auto-calculates scores on Leads, Opportunities, Accounts, and Contacts at save time.

### Architecture

```
ScoringRule ──1:N──> ScoringCriterion ──1:N──> ScoringCondition
                              │
                    EmailActivityScoring (bonus for email engagement)
```

### 10a. ScoringRule

Top-level rule scoped to a CRM module.

| Field | Type | Description |
|-------|------|-------------|
| `name` | `CharField` | Rule name |
| `module` | `CharField` | Target entity: `lead`, `opportunity`, `account`, `contact` |
| `is_active` | `BooleanField` | Enable/disable the rule |

### 10b. ScoringCriterion

A group of conditions that awards or subtracts points when all conditions match.

| Field | Type | Description |
|-------|------|-------------|
| `rule` | `FK(ScoringRule)` | Parent rule |
| `points` | `IntegerField` | Points to award/subtract |
| `operation_type` | `CharField` | `add` or `sub` |
| `order` | `PositiveIntegerField` | Evaluation order |

### 10c. ScoringCondition

A single field comparison against the entity's data.

| Field | Type | Description |
|-------|------|-------------|
| `criterion` | `FK(ScoringCriterion)` | Parent criterion |
| `field` | `CharField` | Model field to evaluate (e.g., `annual_revenue`, `industry`) |
| `operator` | `CharField` | Comparison: `equals`, `contains`, `gt`, `lt`, `between`, `is_empty`, etc. |
| `value` | `CharField` | Value to compare against |
| `logical_operator` | `CharField` | `and` / `or` — how to combine with next condition |
| `order` | `PositiveIntegerField` | Evaluation order |

### 10d. EmailActivityScoring

Bonus scoring for email engagement events.

| Field | Type | Description |
|-------|------|-------------|
| `rule` | `FK(ScoringRule)` | Parent rule |
| `activity_type` | `CharField` | `opened`, `clicked`, or `bounced` |
| `points` | `IntegerField` | Points awarded (default: 10) |

### How Scoring Works

The `compute_score()` function (`leads/utils.py`) runs on every `pre_save` via signals:

1. Determines the module from the model type (Lead → `lead`, Opportunity → `opportunity`, etc.)
2. Fetches all active `ScoringRule` records for that module
3. For each rule, evaluates its `ScoringCriterion` records in order
4. Each criterion checks its `ScoringCondition` list — all conditions must match (combined via `and`/`or`)
5. If a criterion matches, its `points` are added or subtracted
6. The total is stored in the entity's score field (`lead_score`, `opportunity_score`, `account_score`, `contact_score`)

**Example**: A Lead with `industry = "Technology"` and `annual_revenue > $1M` might get +30 points, moving it from "Cold" to "Warm" priority.

---

## Module Relationship Flow — End to End Example

```
                          CAMPAIGN
                     "Google Ads Q2 2026"
                      budget: $5,000
                            │
              (form submission / landing page)
                            │
                            ▼
                           LEAD
                    Jane Smith (jane@pixelcraft.io)
                    Source: Website | Score: 30
                    Status: New → Contacted → Qualified
                            │
                    (convert lead)
                            │
          ┌─────────────────┼────────────────────┐
          ▼                 ▼                     ▼
      ACCOUNT          CONTACT             OPPORTUNITY
  Pixelcraft Design   Jane Smith        Pixelcraft - PM Tool
  Industry: Tech      Role: Decision    Amount: $15,000
  Revenue: $5M         Maker            Stage: Negotiation (60%)
          │                              Forecast: Best Case
          │                              Close: June 30
          │                                   │
          │                                   ▼
          │                           FORECAST (Q3 2026)
          │                           Commit: $450k | Closed: $200k
          │                           Gap: -$400k
          │                                   │
          │                                   ▼
          │                           (deal won)
          │                                   │
          └───────────────────────────────────┘
                                              │
                                              ▼
                                        REPORT / DASHBOARD
                                      - Funnel: Q2 Pipeline
                                      - Bar: Rep Performance
                                      - Daily Sales Dashboard
```
