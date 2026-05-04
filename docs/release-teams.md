# Release teams — areas of ownership

Source: `AlocetSystem.dbo.ReleaseTeam` on prod1 (172.31.121.125).
Pulled: 2026-05-04. Refresh by re-running the query at the bottom.

Use this to route an alert / incident / ticket to the team that owns the affected feature area.

---

## Active teams

### Admin — *Platform Team*
- **Areas:** Platforms (Classic / New / Public), Authentication (Signin / SSO / UserManagement), Platform Services (Preferences / Display / Audit Trail), Multi-Tenant
- **Slack:** `#team-admin` · user group `@admin` · alerts → webhook `B03U3LD1MS9`
- **PM Slack ID:** `U06JK85SH6X`
- **Email:** team-admin@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — Admin tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.hztl3tpzys92)

### Connect — *Integrations Team*
- **Areas:** Accounting Sync (QB / XERO), Third-Party Integrations (Outlook / Gmail / …), Zapier
- **Slack:** `#team-connect` · user group `@connect` · alerts → webhook `B08KQ83KNQ0`
- **PM Slack ID:** `UQBBRQ1PW`
- **Email:** team-connect@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — Connect tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.cctg2zm9nf5l)

### CRM Experience
- **Charter line:** *We make it easy for our users to manage, nurture, and support their customers.*
- **Areas:** Actions, App Routine, App Install / Update, Designer, Report Designer, Notifications, Tables & Fields, Contact Management & Cases stock apps, Portal, SMS
- **Slack:** `#team-crm-experience` · user group `@crm-experience` · alerts → webhook `B08KH16DG4T`
- **PM Slack ID:** `U25VBLYKU`
- **Email:** team-customer-management@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — CRM Experience tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.y1y6r3a9lwkz)

### DevOps
- **Areas:** Architecture, Security, Infrastructure, Tooling
- **Charter line:** *Development (Dev) and IT Operations (Ops)*
- **Slack:** `#team-devops` · user group `@devops` · no alert webhook configured
- **PM Slack ID:** `U25VBLYKU`
- **Email:** devops@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`

### Growth — *Activation Team*
- **Areas:** Signup, Onboarding, Discovery, Analytics, Marketplace, Subscription
- **Slack:** `#team-growth` · user group `@growth` · alerts → webhook `B02LVRVDE90`
- **PM Slack ID:** `U04NZ63487J`
- **Email:** team-growth@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — Growth tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.7f94obibzxz0)

### No Code Next Gen — *No Code Easy Team*
- **Areas:** Making No Code Easy — AppBuilder, AI, Actions
- **Slack:** `#team-no-code-next-gen` · user group `@no code next gen` · alerts → webhook `B08JW7L2ZRU`
- **PM Slack ID:** `U0BDZS6PK`
- **Email:** team-no-code-next-gen@method.me
- **Jira project:** **NCNG** · ready-to-deploy statuses: `Done Test` *(only team that doesn't use the standard Ready/To Deploy gating)*
- **Charter:** [Google Doc — NCNG tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.34na4ch66tyd)

### Service Delivery — *Field Service Team*
- **Areas:** Mobile, Field Services, Scheduling, Calendar
- **Slack:** `#team-service-delivery` · user group `@service delivery` · alerts → webhook `B08CPU8HEG1`
- **PM Slack ID:** `U030LMB4ABZ`
- **Email:** team-service-delivery@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — Service Delivery tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.8kogeq8cyu9#bookmark=id.xlm3wwss9ngj)

### Transactions — *Payments and Invoices Teams*
- **Areas:** Portals, Payments, Invoices and Sales Receipts
- **Slack:** `#team-transactions` · user group `@transactions` · alerts → webhook `B063S8NBW0M`
- **PM Slack ID:** `U25VBLYKU`
- **Email:** team-transactions@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — Transactions tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.vnd933unr9ev#bookmark=id.ec09y2v8litd)

### Vertical App Experience
- **Charter line:** *helping users identify, prioritize, manage and close sales*
- **Areas:** Estimates, Opportunities, Sales Orders, Proposals
- **Slack:** `#team-vertical-app-experience` · user group `@vertical-app-experience` · alerts → webhook `B063S8NBW0M` *(shared with Transactions)*
- **PM Slack ID:** `U086QB1HTUP`
- **Email:** team-sales-management@method.me
- **Jira project:** PL · ready-to-deploy statuses: `Ready To Deploy`, `To Deploy`
- **Charter:** [Google Doc — Vertical App Experience tab](https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.krb8uo317o7v)

### Department *(placeholder)*
- Active row with no metadata. Likely a synthetic parent / catch-all entry — **don't route alerts here**.

---

## Inactive teams (kept for historical context)

These show up in old Jira tickets and Slack archives but are no longer the right routing target.

| Team | Replaced by / what it was |
|---|---|
| AppCentrix | (no notes) |
| Data | "old blackops data team" |
| Impact | Runtime team — Runtime Screens, Services, App Install and Management, Stock App Empowerment. Folded into other teams. |
| Integrations | Old Connect — same area definition (QB/XERO sync, Outlook/Gmail, Zapier). **Use Connect.** |
| Olympus | "old runtime team" |
| Stock Apps | All Stock Apps and Offerings (CRM, Proposals, FieldService, Donor) — re-combined then split. |
| Stock Apps: Field Service | Folded into Service Delivery. |
| Stock Apps: IT/Pro/Tertiary | IT, Professional services, Donor. |
| Stock Apps: MWD/CRM | Manufacturing, Wholesale, Distribution + CRM. Folded into CRM Experience. |

---

## Quick lookup — area → team

When an alert mentions a feature, this is the team that owns it.

| Feature area | Team |
|---|---|
| Actions, App Routine | CRM Experience *(also touched by NCNG via App Builder / AI)* |
| App Builder, AI | No Code Next Gen |
| App Install / Update | CRM Experience |
| Architecture, Security, Infrastructure, Tooling | DevOps |
| Audit Trail | Admin |
| Authentication, Signin, SSO, User Management | Admin |
| Calendar | Service Delivery |
| Cases (stock app) | CRM Experience |
| Contact Management (stock app) | CRM Experience |
| Designer, Report Designer | CRM Experience |
| Discovery | Growth |
| Estimates | Vertical App Experience |
| Field Services | Service Delivery |
| Gmail integration | Connect |
| Invoices | Transactions |
| Marketplace | Growth |
| Mobile | Service Delivery |
| Multi-Tenant | Admin |
| Notifications | CRM Experience |
| Onboarding | Growth |
| Opportunities | Vertical App Experience |
| Outlook integration | Connect |
| Payments | Transactions |
| Platforms (Classic / New / Public) | Admin |
| Platform Services (Preferences / Display) | Admin |
| Portal | CRM Experience |
| Portals (payment portals) | Transactions |
| Proposals | Vertical App Experience |
| QuickBooks sync, Xero sync | Connect |
| Sales Orders | Vertical App Experience |
| Sales Receipts | Transactions |
| Scheduling | Service Delivery |
| Signup | Growth |
| SMS | CRM Experience |
| Subscription | Growth |
| Tables & Fields | CRM Experience |
| Zapier | Connect |
| Analytics | Growth |

---

## How to refresh

```bash
"/c/Users/Benjamin Grady/AppData/Local/Microsoft/WindowsApps/python3" \
  C:/MethodDev/method-db-tools/scripts/db_query.py -c prod1 execute \
  -d AlocetSystem -f json -q \
  "SELECT RecordID, ReleaseTeam, isActive, TeamArea, TeamDescription, TeamCharter,
          JiraProject, TeamSlackChannelText, TeamSlackUserGroup, TeamSlackAlertChannel,
          TeamEmail, ProductManagerSlackMemberID, JiraReadyToDeployStatus
     FROM ReleaseTeam ORDER BY isActive DESC, ReleaseTeam"
```

Schema (18 columns, 19 rows as of pull date) lives in
`C:/MethodDev/method-db-tools/db-knowledge/databases/AlocetSystem/tables/ReleaseTeam.json`.
