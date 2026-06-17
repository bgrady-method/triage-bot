> **ADOPTED — authoritative ownership / alert-routing source for the triage routine.**
> This is the source of truth for *which team owns a given service / component / project*.
> Triage uses it to **identify** the owning team for every alert and to name which team it
> *would* tag — but the routine **NEVER tags a team** (no @-usergroup mention, no post to a
> team channel or webhook). See `prompt.md` step 4.1a and Hard rule #13.
>
> **Secrets scrubbed:** the `TeamSlackAlertChannel` webhook URLs (live Slack incoming-webhooks)
> have been redacted from this copy. Channel names and usergroup handles are kept for
> identification only. Pull the live webhooks from `AlocetSystem.dbo.ReleaseTeam` if ever needed.

# M:Architecture — "Ownership" Screen: Data & SQL Provenance

> Internal software-ownership documentation screen for the Method engineering
> department. This document records every grid on the screen, the exact data
> source behind it, the SQL to reproduce it, and an export of the data.

## 1. Identity / where this lives

| Attribute | Value |
|---|---|
| URL | `https://method.method.me/apps/Default.aspx#/fca2761a-67a8-46eb-be6f-1d78085b4fe1` |
| Account (tenant) | **alocetsystem** (Method's internal account) |
| App | **M:Architecture** — App ID `9c5ecefc-e102-4c40-b97e-a9b500d4f81b` |
| Screen | **M:Ownership** — Screen ID `fca2761a-67a8-46eb-be6f-1d78085b4fe1` (this is the screen id, not the app id) |
| Screen type | V3 (legacy designer; `IsV4Screen = false`) — grid configs stored in Mongo `Runtime.Core.ScreenBase` |
| Runtime data API | `POST https://alocetsystem.method.me/runtime/api/v1/datatable/fca2761a-67a8-46eb-be6f-1d78085b4fe1` (one call per grid) |
| SQL database | **AlocetSystem** (single tenant — `TenantID = 1`) |
| Grids on screen | 3 (all `DataTable` controls) |

## 2. How this was reconstructed (provenance method)

1. Opened the live screen on prod (`method.method.me`) and captured the three
   `runtime/api/v1/datatable` responses — confirming three grids and their
   returned column/field names and rows.
2. Pulled the screen definition from MongoDB
   (`alocetsystem` DB → `Runtime.Core.ScreenBase`, `_id = fca2761a-…`). The three
   `DataTable` controls carry the bound object (`viewFriendlyName`), the saved
   views (`viewList`: columns, filtering, sorting) and the default view
   (`defaultViewFilter`).
3. Mapped each bound object to its SQL view in **AlocetSystem** and read the view
   definitions (`OBJECT_DEFINITION`) to capture the exact column list, the
   foreign-key join, and the soft-delete predicate.
4. Ran the reproduced SELECTs to export the data below.

> **Data freshness:** the row export below was run against the **local**
> AlocetSystem database (stale snapshot) per request — the *Teams* grid count
> (10) matches prod exactly; *Components* / *Projects* counts may lag prod. The
> **SQL is the authoritative artifact** and runs unchanged against prod.

## 3. Shared schema facts

All three source tables follow Method's standard shape and each is exposed
through a `view<Table>` that the grid binds to:

* Every `view<Table>` filters soft-deleted rows:
  `WHERE (intMarkedForDeletion IS NULL OR intMarkedForDeletion NOT IN (1,2,3))`.
* `ReleaseComponents` and `MethodReleaseProject` store the owning team as
  `TeamRef` (int FK → `ReleaseTeam.RecordID`). Their views resolve it via a
  `LEFT OUTER JOIN ReleaseTeam` and expose it as `Team` (the team's name) plus
  `Team_RecordID` (the raw FK).
* `AlocetSystem` is single-tenant here (`TenantID = 1`), so no tenant predicate
  is needed to reproduce the grids.

### Saved-view filters (operators decoded)

Each grid ships several saved views; the screen opens on the **Active** one.

| Saved view | WHERE clause |
|---|---|
| Active * | `isActive = 1` |
| Inactive * | `isActive = 0` |
| All * | `<nameField> <> ''` (name is not blank → effectively all live rows) |
| Unassigned * | `TeamRef IS NULL` (team is blank) |

---

## 4. Grid 1 — "Teams and Areas"  (control `TeamsandAreas`)

* **Bound object:** `ReleaseTeam` → SQL view `dbo.viewReleaseTeam`
* **Default view:** *Active Teams* (`_id 1eb66a4e-90ae-6498-defa-aa45318153f1`)
* **Filter:** `isActive = 1`  •  **Sort:** `ReleaseTeam ASC`
* **Visible columns:** ReleaseTeam, TeamDescription, TeamArea, TeamSlackChannelText,
  TeamSlackUserGroup, TeamCharter, TeamEmail, isActive, TeamSlackAlertChannel
  *(RecordID and ProductManagerSlackMemberID present in view but hidden)*

**SQL — as the runtime runs it (view-based):**

```sql
SELECT ReleaseTeam, TeamDescription, TeamArea, TeamSlackChannelText,
       TeamSlackUserGroup, TeamCharter, TeamEmail, isActive, TeamSlackAlertChannel
FROM AlocetSystem.dbo.viewReleaseTeam WITH (NOLOCK)
WHERE isActive = 1
ORDER BY ReleaseTeam ASC;
```

**SQL — fully inlined (no dependency on the view):**

```sql
SELECT ReleaseTeam, TeamDescription, TeamArea, TeamSlackChannelText,
       TeamSlackUserGroup, TeamCharter, TeamEmail, isActive, TeamSlackAlertChannel
FROM AlocetSystem.dbo.ReleaseTeam WITH (NOLOCK)
WHERE isActive = 1
  AND (intMarkedForDeletion IS NULL OR intMarkedForDeletion NOT IN (1,2,3))
ORDER BY ReleaseTeam ASC;
```

**Data (10 rows):**

| ReleaseTeam | TeamDescription | TeamArea | TeamSlackChannelText | TeamSlackUserGroup | TeamCharter | TeamEmail | isActive | TeamSlackAlertChannel |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Admin | Platform Team | Platforms (Classic/New/Public), Authentication (Signin/SSO/UserManagement), Platform Services (Preferences/Display/Audit Trail), Multi-Tenant | #team-admin | @admin | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.hztl3tpzys92">link</a> | team-admin@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| Connect | Integrations Team | Accounting Sync (QB/XERO), Third Party Integrations (Outlook/Gmail/), Zapier | #team-connect | @connect | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.cctg2zm9nf5l">link</a> | team-connect@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| CRM Experience | We make it easy for our users to manage, nurture, and support their customers. | Actions, App Routine, App Install/Update, Designer, Report Designer, Notifications, Tables & Fields, Contact Management & Cases stock apps, Portal, SMS | #team-customer-management | @customer-management | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.y1y6r3a9lwkz">link</a> | team-customer-management@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| Department |  |  |  |  |  |  | True |  |
| DevOps | Development (Dev) and IT Operations (Ops) | Architecture, Security, Infrastructure, Tooling | #team-devops | @devops |  | devops@method.me | True |  |
| Growth | Activation Team | Signup, Onboarding, Discovery, Analytics, Marketplace, Subscription | #team-growth | @growth | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.7f94obibzxz0">link</a> | team-growth@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| No Code Next Gen | No Code Easy Team | Making No Code Easy - AppBuilder, AI, Actions | #team-no-code-next-gen | @no code next gen | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.34na4ch66tyd">link</a> | team-no-code-next-gen@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| Service Delivery | Field Service Team | Mobile, Field Services, Scheduling, Calendar | #team-service-delivery | @service delivery | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.8kogeq8cyu9#bookmark=id.xlm3wwss9ngj">link</a> | team-service-delivery@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| Transactions | Payments and Invoices Teams | Portals, Payments, Invoices and Sales Receipts | #team-transactions | @transactions | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.vnd933unr9ev#bookmark=id.ec09y2v8litd">link</a> | team-transactions@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |
| Vertical App Experience | helping users identify, prioritize, manage and close sales | Estimates, Opportunities, Sales Orders, Proposals | #team-sales-management | @sales management | <a href="https://docs.google.com/document/d/1qp-awusAr-RSRP02aHaX6FiAIg1yzzU8_ApoHfiP0cs/edit?tab=t.krb8uo317o7v">link</a> | team-sales-management@method.me | True | [redacted-live-webhook — see AlocetSystem.dbo.ReleaseTeam] |

---

## 5. Grid 2 — "Ownership by Component"  (control `OwnershipbyComponent`)

* **Bound object:** `ReleaseComponents` → SQL view `dbo.viewReleaseComponents`
* **Default view:** *Active Components* (`_id e1ddd1c4-2c67-f97a-5cb7-c6af52caf50a`)
* **Filter:** `isActive = 1`  •  **Sort:** `Component ASC`
* **Visible columns:** Component, Team, IsStockApp, isActive  *(RecordID hidden)*
* **FK:** `Team` is `ReleaseComponents.TeamRef` → `ReleaseTeam.RecordID`, resolved to the team name.

**SQL — as the runtime runs it (view-based):**

```sql
SELECT Component, Team, IsStockApp, isActive
FROM AlocetSystem.dbo.viewReleaseComponents WITH (NOLOCK)
WHERE isActive = 1
ORDER BY Component ASC;
```

**SQL — fully inlined (base table + FK join):**

```sql
SELECT  c.Component,
        t.ReleaseTeam AS Team,
        c.IsStockApp,
        c.isActive
FROM AlocetSystem.dbo.ReleaseComponents c WITH (NOLOCK)
LEFT OUTER JOIN AlocetSystem.dbo.ReleaseTeam t WITH (NOLOCK)
       ON c.TeamRef = t.RecordID
WHERE c.isActive = 1
  AND (c.intMarkedForDeletion IS NULL OR c.intMarkedForDeletion NOT IN (1,2,3))
ORDER BY c.Component ASC;
```

**Data (105 rows):**

| Component | Team | IsStockApp | isActive |
| --- | --- | --- | --- |
| Accounting / Business Logic | Connect | False | True |
| Accounts | Transactions | True | True |
| Actions | No Code Next Gen | False | True |
| Activities | CRM Experience | True | True |
| Analytics | Growth | False | True |
| App Install/Update | CRM Experience | False | True |
| App Ribbons | Vertical App Experience | False | True |
| App Routine | CRM Experience | False | True |
| Archive | Connect | False | True |
| Attachments | Vertical App Experience | False | True |
| AuditTrail | Admin | False | True |
| Billing / Subscription | Growth | False | True |
| Bills | Vertical App Experience | True | True |
| Button | Vertical App Experience | False | True |
| Button Menu | Vertical App Experience | False | True |
| Calendar | Service Delivery | False | True |
| Cases | CRM Experience | True | True |
| Chart | Vertical App Experience | False | True |
| Checkbox | Vertical App Experience | False | True |
| Classes | Transactions | True | True |
| Classic | Admin | False | True |
| Contacts | CRM Experience | True | True |
| Credit Memos | Stock Apps | False | True |
| Criteria Builder | CRM Experience | False | True |
| DAL | Impact | False | True |
| DateTime Picker | Vertical App Experience | False | True |
| Designer | No Code Next Gen | False | True |
| Display | Admin | False | True |
| Donations | Transactions | True | True |
| Donor Pages | Transactions | True | True |
| Dropdown | Vertical App Experience | False | True |
| Email | Transactions | False | True |
| Email Builder | Vertical App Experience | False | True |
| Email Campaigns | Transactions | True | True |
| Estimates | Vertical App Experience | True | True |
| Export | Admin | False | True |
| Expression Editor | CRM Experience | False | True |
| Field Crew | Service Delivery | True | True |
| Gallery | Vertical App Experience | False | True |
| Gmail Sidebar | Connect | False | True |
| Google Calendar | Connect | False | True |
| Grids | Vertical App Experience | False | True |
| HTML Editor | Vertical App Experience | False | True |
| Icon | Vertical App Experience | False | True |
| Import | Admin | False | True |
| Internal |  | False | True |
| Invoices | Transactions | True | True |
| Items | Vertical App Experience | True | True |
| Logstash |  | False | True |
| MailChimp | Connect | False | True |
| Manage Apps | Vertical App Experience | False | True |
| Map | Service Delivery | False | True |
| Migration Service | DevOps | False | True |
| MiURL | Transactions | False | True |
| Mobile | Service Delivery | False | True |
| Mobile App | Service Delivery | False | True |
| Multi-Tenant | Admin | False | True |
| Notifications | CRM Experience | False | True |
| Opportunities | Vertical App Experience | True | True |
| Outlook Gadget | Connect | False | True |
| Payment processing | Transactions | False | True |
| Payments | Transactions | True | True |
| Permissions | Admin | False | True |
| Permissions | Admin | False | True |
| Picture | Vertical App Experience | False | True |
| Pixel Tracker | Growth | False | True |
| Portals | CRM Experience | False | True |
| Profile | Admin | False | True |
| Proposals | Vertical App Experience | True | True |
| Public | Admin | False | True |
| Purchase Orders | Vertical App Experience | True | True |
| QBDT | Connect | False | True |
| QBO | Connect | False | True |
| Radio Button | Vertical App Experience | False | True |
| Recurrence Widget | Service Delivery | False | True |
| Report Designer | CRM Experience | False | True |
| REST API | Connect | False | True |
| Sales Orders | Vertical App Experience | True | True |
| Sales Receipts | Transactions | True | True |
| Sales Reps | Vertical App Experience | True | True |
| Section | Vertical App Experience | False | True |
| Send Email | Transactions | True | True |
| Shell | Admin | False | True |
| Show Message | CRM Experience | False | True |
| Signature | Vertical App Experience | False | True |
| Signin | Admin | False | True |
| Signup | Growth | False | True |
| Style/Css |  | False | True |
| Support Tools | Admin | False | True |
| Sync Engine | Connect | False | True |
| SyncLog | Connect | False | True |
| System Pages | Admin | False | True |
| Tables & Fields | Admin | False | True |
| Terms | Transactions | True | True |
| Text | Vertical App Experience | False | True |
| Text Input | Vertical App Experience | False | True |
| Time Tracking | Service Delivery | False | True |
| Toggle | Vertical App Experience | False | True |
| Universal Search | Admin | False | True |
| Users / User Management | Admin | False | True |
| Web To Lead | Vertical App Experience | True | True |
| Work Orders | Service Delivery | True | True |
| Xero | Connect | False | True |
| Xero | Connect | False | True |
| Zapier | Connect | False | True |

---

## 6. Grid 3 — "Ownership by Project"  (control `OwnershipbyProject`)

* **Bound object:** `MethodReleaseProject` → SQL view `dbo.viewMethodReleaseProject`
* **Default view:** *Active Projects/Areas* (`_id 94a3eaf1-0fa3-0aa8-7165-571e654feffc`)
* **Filter:** `isActive = 1`  •  **Sort:** `Project ASC`
* **Visible columns:** Project, Team, Type, Description, Location, isActive, loggingId  *(RecordID hidden)*
* **FK:** `Team` is `MethodReleaseProject.TeamRef` → `ReleaseTeam.RecordID`, resolved to the team name.

**SQL — as the runtime runs it (view-based):**

```sql
SELECT Project, Team, Type, Description, Location, isActive, loggingId
FROM AlocetSystem.dbo.viewMethodReleaseProject WITH (NOLOCK)
WHERE isActive = 1
ORDER BY Project ASC;
```

**SQL — fully inlined (base table + FK join):**

```sql
SELECT  p.Project,
        t.ReleaseTeam AS Team,
        p.Type,
        p.Description,
        p.Location,
        p.isActive,
        p.loggingId
FROM AlocetSystem.dbo.MethodReleaseProject p WITH (NOLOCK)
LEFT OUTER JOIN AlocetSystem.dbo.ReleaseTeam t WITH (NOLOCK)
       ON p.TeamRef = t.RecordID
WHERE p.isActive = 1
  AND (p.intMarkedForDeletion IS NULL OR p.intMarkedForDeletion NOT IN (1,2,3))
ORDER BY p.Project ASC;
```

**Data (156 rows):**

| Project | Team | Type | Description | Location | isActive | loggingId |
| --- | --- | --- | --- | --- | --- | --- |
| App Accounts | Stock Apps | runtimeapp | The Accounts App lets you create and modify transactional accounts and sub-accounts that sync with QuickBooks.  | https://method.method.me/apps/Default.aspx#/subscription/808774e8-999b-41ad-97ab-01aad7d4f8e1 | True |  |
| App Activities | CRM Experience | runtimeapp | The Activities App lets you keep a full record of all your interactions with your company and your contacts – customers, vendors, leads and more. its part of the contact management pack. | https://method.method.me/apps/Default.aspx#/apps/bd5d506c-ca7c-46f5-8dbd-a2d4009db6c3/screens | True |  |
| App Bills | Vertical App Experience | runtimeapp | Method's Bills App, part of the Purchase Transactions pack.  Bills are saved as soon as you create a bill and select a vendor for that bill, even without hitting the save button. | https://method.method.me/apps/Default.aspx#/subscription/d717ac52-7743-42ce-bade-55f21e06dbc6 | True |  |
| App Cases | CRM Experience | runtimeapp | The Cases App creates support cases to help keep track of all activities pertaining to a specific customer or internal issue (complaint, product request, etc), as part of the Case management Pack. | https://method.method.me/apps/Default.aspx#/apps/d0da6ee9-1c38-4644-88c6-a51e009c5212/screens | True |  |
| App Classes | Stock Apps | runtimeapp | The Classes App allows you to manage your classes synced from QuickBooks as well as create unique classes to assign to transactions. | https://method.method.me/apps/Default.aspx#/apps/cee3180d-3fde-47e5-9990-a38400b7b9af/screens | True |  |
| App Customers & Leads | CRM Experience | runtimeapp | The Customers & Leads App lets you organize and manage your company's relationships with customers and leads by creating and maintaining contacts for each.  | https://method.method.me/apps/Default.aspx#/apps/92ce0e6b-763d-4931-b60e-a2d40170e915/screens | True |  |
| App Donations | Transactions | runtimeapp | The Donations App lets you easily keep track of donations you receive from your donors and maintain communication with them.  The app is part of the Donor Management Pack. | https://m11richardp.method.me/apps/Default.aspx#/marketplace/430b710f-8cf0-41f8-a481-9d09ad2d6322 | True |  |
| App Donor Pages | Transactions | runtimeapp | The Donor Pages App lets you accept online donations through a personalized donation webpage.  | https://m11richardp.method.me/apps/Default.aspx#/marketplace/430b710f-8cf0-41f8-a481-9d09ad2d6322 | True |  |
| App Email Campaigns | Vertical App Experience | runtimeapp | The Email Campaigns App is designed to create and send mass emails to filtered contact lists, right from your Method account, as part of the email campaigns pack. | https://method.method.me/apps/Default.aspx#/apps/977ec769-b6d2-4ecf-bfcc-06a1d40072b1/screens | True |  |
| App Estimates | Vertical App Experience | runtimeapp | This app is part of the Sales Transactions Pack.  Estimates are the customer quote, to be accepted or rejected by the customer.  | https://method.method.me/apps/Default.aspx#/apps/e5ab3ab8-7a93-4e7e-9748-a33b00d8ce3b/screens | True |  |
| App Field Crew | Service Delivery | runtimeapp | The Field Crew app is designed for your field team to quickly view work order details, add items, and track time on the job. It comes with a mobile friendly design | https://method.method.me/apps/Default.aspx#/subscription/00954fd9-3957-4f05-9642-326afa50b576 | True |  |
| App Invoices | Transactions | runtimeapp | The Invoices App lets you effectively manage your customers' invoices and keep an accurate record of your transactions. They sync to accounting and are part of the sales transaction pack. | https://method.method.me/apps/Default.aspx#/apps/ec3cd016-e8de-4244-b8cf-a29300ae95eb/screens | True |  |
| App Items | Vertical App Experience | runtimeapp | The Items App gives Method users the ability to create items that are synced to QuickBooks. You can also edit existing items, changing prices, units of measurement, and applicable accounts | https://method.method.me/apps/Default.aspx#/apps/52eb4233-4a4d-4335-a412-a37e00c9f757/screens | True |  |
| App Jobs | Service Delivery | runtimeapp | Plan, track, and manage every job from start to finish — all in one place. |  | True |  |
| App Opportunities | Vertical App Experience | runtimeapp | The Opportunities App lets you manage your company's potential business every step of the way while providing the most important metrics in easy-to-read charts | https://m11richardp.method.me/apps/Default.aspx#/apps/62d5aca0-a2fb-4d62-8af4-a38100a17531/screens | True |  |
| App Payments | Transactions | runtimeapp | The Payments App works with payment gateways and lets you keep an accurate record of all payments received by your company – cash transactions, PayPal, credit cards and more. | https://method.method.me/apps/Default.aspx#/apps/8af71562-f84f-4988-abc6-a3a7009daad2/screens | True |  |
| App Proposals | Vertical App Experience | runtimeapp | The Proposals App program will automate the process of getting your customers to receive and accept engagement letters.  Once accepted, you can set up recurring invoices, as well as recurring payments if you have a payment gateway added. | https://method.method.me/apps/Default.aspx#/marketplace/a9462de6-8272-4938-bf1c-481cf156e3c0 | True |  |
| App Purchase Orders | Vertical App Experience | runtimeapp | Purchase Orders are part of the purchase transactions pack.  Items to be purchased are issued by a business’ purchasing department when placing an order with its vendors or suppliers | https://method.method.me/apps/Default.aspx#/subscription/d717ac52-7743-42ce-bade-55f21e06dbc6 | True |  |
| App Sales Orders | Vertical App Experience | runtimeapp | The Sales Order App allows you to keep an accurate record of what your company has sold and when. Unlike an invoice, a sales order is meant to record what your company needs to complete a customer's order – parts, inventory, services, and so on. | https://method.method.me/apps/Default.aspx#/apps/55b7fa26-9d45-400d-829f-a3610098567c/screens | True |  |
| App Sales Receipts | Transactions | runtimeapp | Method's Sales Receipts App allows you to create receipts for your customers to keep track of their own purchases. | https://method.method.me/apps/Default.aspx#/apps/2fb50ef2-476e-4840-a2b7-a29300b3990d/screens | True |  |
| App Sales Reps | Vertical App Experience | runtimeapp | The Sales Rep app lets you assign the Sales Rep title to existing employees and vendors in QuickBooks Desktop. | https://method.method.me/apps/Default.aspx#/apps/56e30438-cfc3-4dcd-8029-a38400b8051f/screens | True |  |
| App Schedule | Service Delivery | runtimeapp | Manage visits in multiple calendar views, schedule work from an unscheduled waitlist, and create estimate or work order visits linked to jobs. |  | True |  |
| App Send Email | Transactions | runtimeapp | The Send Email App lets you send emails directly from Method with the click of a button. This app works with other apps in Method to ensure notifications get to your customers in a timely and relevant manner.  | https://method.method.me/apps/Default.aspx#/apps/c8f59c6f-a5ac-4a04-8e3a-a3ad00c5602f/screens | True |  |
| App Terms | Stock Apps | runtimeapp | The Terms App lets you create new terms to apply to your transactions. Using this app means creating custom terms reflecting payment requirements is easier than ever: no switching to QuickBooks to make the changes. | https://method.method.me/apps/Default.aspx#/apps/fff87621-a6a0-4048-a641-a38400b7da64/screens | True |  |
| App Time Tracking | Stock Apps | runtimeapp | The Time Tracking App lets you create and modify time tracking entries that sync with QuickBooks (Online or Desktop.) Time tracking entered through Method will be synced to QuickBooks under the customer you create it for. | https://method.method.me/apps/Default.aspx#/marketplace/2e34b28d-de8f-48f3-be26-32428f0da13c | True |  |
| App Vendors | CRM Experience | runtimeapp | The Vendors App lets you organize and manage your company's relationships with vendors by creating and maintaining contacts for each.  |  | True |  |
| App Web to Lead | Vertical App Experience | runtimeapp | The Web to Lead app gives you a web form to collect information from potential customers (or leads). A lead is a potential customer. Therefore, leads are not synced to QuickBooks until the lead is converted to a customer.  | https://method.method.me/apps/Default.aspx#/apps/c8f30f61-1667-437d-a656-a4f2008a0cfd/screens | True |  |
| App Work Orders | Service Delivery | runtimeapp | The Work Orders app is the center of Method:Field Services and it's purpose to allow you to manage one-time and recurring work orders. | https://method.method.me/apps/Default.aspx#/marketplace/356ca17a-1082-4e0c-92f2-b45a52b68f2b | True |  |
| app-builder | No Code Next Gen |  |  |  | True |  |
| approutine-agent | CRM Experience |  |  |  | True |  |
| app-update-agent | CRM Experience |  |  |  | True |  |
| designer-core-api | No Code Next Gen |  |  |  | True |  |
| EDA-stack | Integrations |  | EDA Projects |  | True |  |
| emailgadget-signin-ui | Integrations |  |  |  | True |  |
| email-monitor-agent | Transactions |  |  |  | True |  |
| email-public-pages | Transactions |  |  |  | True |  |
| events-subscribers-sync | Integrations |  |  |  | True |  |
| events-subscribers-tags | Vertical App Experience |  |  |  | True |  |
| event-subscriber-audittrail | Admin |  |  |  | True |  |
| gmail-addon-ui | Integrations |  |  |  | True |  |
| identity-server | Admin |  |  |  | True | method-oauth- |
| internal-attribution-api | Growth | service | An internal api tool ran daily to help marketing with campaign attribution of  pixeltracker touch points.  Also used by dev to Split Growth metrics for Signup and Onboarding Completion rates. | https://github.com/methodcrm/internal-attribution-api | True |  |
| internal-dataminer-api | Growth | service | An internal api we hit nightly with an app routine, it scrapes all customer accounts for Quickbooks and account data, last acess dates, puts this in alocet system > customermethodaccount. | https://github.com/methodcrm/internal-dataminer-api | True |  |
| internal-migration-api | Impact |  |  |  | True |  |
| internal-saasanalytics-api | Growth | service | Used to get Saas Analytics based off alocetsystem data. Inovices and Period comparisons to excel files.  Daily Deltas.  There are also some endpoints for Merge and Swap Contacts. | https://github.com/methodcrm/internal-saasanalytics-api | True |  |
| legacy-authentication-api | Admin |  | legacy authentication service used to signin to new/classic and for new auth callbacks | https://github.com/methodcrm/legacy-authentication-api | True |  |
| legacy-billingsubscription-api | Growth | service | Used for Subscibing to method, getting billing status, doing nightly billing runs.  Also does prepay and topup.  Charge by ach or credit card using classic dll nugets | https://github.com/methodcrm/legacy-billingsubscription-api | True |  |
| legacy-bre-api | Impact |  |  |  | True |  |
| legacy-common-core | Integrations |  |  |  | True |  |
| legacy-communityserver-ui | Growth | webapp | forums used by forums.method.me, old asp.net classic site.   Discussions on method classic, legacy api, and classic customization. | https://github.com/methodcrm/legacy-communityserver-ui | True |  |
| legacy-custom-api | Admin |  | legacy custom webservice asmx, we have tools to remove and customers using this endpoint | https://github.com/methodcrm/legacy-custom-api | True |  |
| legacy-email-subscriber | Transactions |  |  |  | True | method-microservices-email- |
| legacy-googlecalendarsync-agent | Integrations |  |  |  | True |  |
| legacy-importexport-ui | Admin |  |  | https://github.com/methodcrm/legacy-importexport-ui | True |  |
| legacy-intercom-agent | Growth | worker | background agent that kicks off nightly to sync user and account data with intercom, a third party analytics app.  Calls legacy-intercom-api to do work. | https://github.com/methodcrm/legacy-intercom-agent | True |  |
| legacy-intercom-api | Growth | service | An internal api that is used to sync analytics data with intercom third party analytics tool. | https://github.com/methodcrm/legacy-intercom-api | True |  |
| legacy-internal-api | Admin |  | mapi is legacy internal api used between new and classic, to be deprecated | https://github.com/methodcrm/legacy-internal-api | True |  |
| legacy-methodcdn-ui | Admin | webapp | A copy of method classic web app, used for sharding js resources for initial loads. | https://github.com/methodcrm/legacy-method-ui | True |  |
| legacy-method-ui | Admin | webapp | method classic ui, legacy method ui platform | https://github.com/methodcrm/legacy-method-ui | True |  |
| legacy-miurl-api | Transactions |  |  |  | True | method-miurl- |
| legacy-miurl-consumer | Transactions |  |  |  | True |  |
| legacy-openid-api | Integrations |  |  |  | True |  |
| legacy-pixeltracker-api | Growth | service | An external webservice used to inject cookies or tracking pixels across various public facing websites and marketing pages.  Used with attribution engine to determine usefulness of ads and campaigns upon signup. | https://github.com/methodcrm/legacy-pixeltracker-api | True |  |
| legacy-public-api | Integrations |  |  |  | True |  |
| legacy-reportgeneration-api | CRM Experience |  |  |  | True | method-reportapi- |
| legacy-requestmgr-agent | Admin |  | legacy request manager agent running on classic servers | https://github.com/methodcrm/legacy-requestmgr-agent | True |  |
| legacy-screenxml-api | Admin |  | legacy classic webapi for generating screen xml for classic ui | https://github.com/methodcrm/legacy-screenxml-api | True |  |
| legacy-syncservice-api | Connect |  |  |  | True | method-microservices-syncservices- |
| legacy-webforms-ui | Admin |  |  | https://github.com/methodcrm/legacy-webforms-ui | True |  |
| Method.Data.RestApi | Integrations |  |  |  | True | restapi- |
| method-nativemobile-ui | Admin | reactnative | native mobile app for android and ios | https://github.com/methodcrm/method-nativemobile-ui | True |  |
| method-notifications-api | CRM Experience |  |  |  | True |  |
| method-platform-ui | Admin | webapp | Method Platform UI for method new (right now public, portal, emailgadget and ui) | https://github.com/methodcrm/method-platform-ui | True | method-platformui- |
| method-portal-ui | Admin |  |  |  | True |  |
| method-public-ui | Admin |  |  |  | True |  |
| method-signin-ui | Admin | webapp | Signin web app for login to method new platform | https://github.com/methodcrm/method-signin-ui | True | method-signin- |
| method-signup-ui | Growth | webapp | A public facing website used to create new method accounts for internal or external use.  Can do AB Tests, as well as allows signups to be posted/submitted from growth.method.me | https://github.com/methodcrm/method-signup-ui | True | method-signup- |
| method-ui | Admin |  |  |  | True |  |
| MN:SystemPage - Accounting Sync | Integrations |  |  |  | True |  |
| MN:SystemPage - API | Integrations |  |  |  | True |  |
| MN:SystemPage - App Routines | CRM Experience |  |  |  | True |  |
| MN:SystemPage - AuditTrail | Admin |  |  |  | True |  |
| MN:SystemPage - Auth Codes | Integrations |  |  |  | True |  |
| MN:SystemPage - Dashboard Angular | CRM Experience |  |  |  | True |  |
| MN:SystemPage - Designer | CRM Experience |  |  |  | True |  |
| MN:SystemPage - Discover Hub | Growth | area | A page in the Method Web app https://method.method.me/apps/Default.aspx#/discover, used to discover how to use method with navatic demos and missions for onboarding in order to drive usage. | https://github.com/methodcrm/method-platform-ui/tree/master/MethodUI/public/react/pages/dashboard/discover | True |  |
| MN:SystemPage - GlobalHelp | Growth | area | Launched from top right corner of Method Web app https://method.method.me/apps, a react panel that loads contextual help articles.  Searches help.method.me in a new window. | https://github.com/methodcrm/method-platform-ui/tree/master/MethodUI/public/react/views/panels/contextual/globalHelp | True |  |
| MN:SystemPage - Gmail Sidebar | Integrations |  |  |  | True |  |
| MN:SystemPage - Google Calendar | Integrations |  |  |  | True |  |
| MN:SystemPage - Import/Export | Admin |  |  |  | True |  |
| MN:SystemPage - Mailchimp | Integrations |  |  |  | True |  |
| MN:SystemPage - Manage Apps | CRM Experience |  |  |  | True |  |
| MN:SystemPage - Outlook Gadget | Integrations |  |  |  | True |  |
| MN:SystemPage - Payment Gateways | Transactions |  |  |  | True |  |
| MN:SystemPage - Reports | CRM Experience |  |  |  | True |  |
| MN:SystemPage - Zapier | Integrations |  |  |  | True |  |
| MN:SystemPage- Dashboard New | Impact |  |  |  | True |  |
| MN:SystemPage- Display | Admin |  |  |  | True |  |
| MN:SystemPage- Email | Transactions |  |  |  | True |  |
| MN:SystemPage- GlobalSearch | Admin |  |  |  | True |  |
| MN:SystemPage- Marketplace | Growth | area | A page in Method Web app https://method.method.me/apps/Default.aspx#/marketplace.  Used to find more apps to install, or to manage access to apps. | https://github.com/methodcrm/method-platform-ui/tree/master/MethodUI/public/src/subscription | True |  |
| MN:SystemPage- Notifications | CRM Experience |  |  |  | True |  |
| MN:SystemPage- Onboarding  Wizard | Growth | area | A page in Method Web app https://method.method.me/apps/Default.aspx#/onboarding-v2.  Used to select which apps to install in the background as you go through the wizard. Uses ms account api. | https://github.com/methodcrm/method-platform-ui/tree/master/MethodUI/public/react/pages/onboarding | True |  |
| MN:SystemPage- Onboarding Checklist | Growth | area | A page in Method Web app https://method.method.me/apps/Default.aspx#/onboarding-v2/survey.  Used to select which apps to install in the background as you go through the wizard.  Uses ms account api | https://github.com/methodcrm/method-platform-ui/tree/master/MethodUI/public/react/pages/onboarding/componentsV2/OnboardingSurveyDialog | True |  |
| MN:SystemPage- Portal | Admin |  |  |  | True |  |
| MN:SystemPage- Subscription | Growth | area | A page in Method Web app https://method.method.me/apps/Default.aspx#/subscription.  The subscription page is used to active a trial to subscriber status, and allows you to see how much you are paying, whether to pay monthly or annually. Uses billing service as its backend. | https://github.com/methodcrm/method-platform-ui/tree/master/MethodUI/public/src/subscription | True |  |
| MN:SystemPage- Tables & Fields | Admin |  |  |  | True |  |
| MN:SystemPage- User Management | Admin |  |  |  | True |  |
| MN:SystemPage- UserProfile | Admin |  |  |  | True |  |
| mobile-notifications-stack | Admin |  |  |  | True | method-microservices-mmobilenotifications- |
| ms-account-api | Admin | service | Account Management Service,  Account Creation and Cancellation, Reinstate. Gets Account info and db cluster info used by all services.  User Management and Tenant Management as well. | https://github.com/methodcrm/ms-account-api | True | method-microservices-account- |
| ms-analytics-api | Growth | service | Old service used to send product analytics to segment, should be deprecated. | https://github.com/methodcrm/ms-analytics-api | True |  |
| ms-apps-api | Impact |  |  |  | True |  |
| ms-archive-api | Integrations |  |  |  | True |  |
| ms-audittrail-api | Admin | service |  |  | True |  |
| ms-authentication-api | Admin | service |  | https://github.com/methodcrm/ms-authentication-api | True | method-microservices-authentication- |
| ms-core | Impact | library | method micro services core components. Used for templating new microservices and nugets | https://github.com/methodcrm/ms-core | True |  |
| ms-documents-api | Vertical App Experience |  |  |  | True |  |
| ms-email-api | Transactions |  |  |  | True | email- |
| ms-gateway-api | Admin | service |  | https://github.com/methodcrm/ms-gateway-api | True | method-gateway- |
| ms-gmail-addon-api | Integrations |  |  |  | True |  |
| ms-google-calendarsync-api | Integrations |  |  |  | True |  |
| ms-identity-api | Admin | service |  | https://github.com/methodcrm/ms-identity-api | True | method-microservices-identity- |
| ms-mailchimp-agent | Integrations |  |  |  | True |  |
| ms-mailchimp-api | Integrations |  |  |  | True |  |
| ms-preferences-api | Admin | service |  | https://github.com/methodcrm/ms-preferences-api | True | method-microservices-preferences- |
| ms-reminder-agent | CRM Experience |  |  |  | True |  |
| ms-schedular-api | CRM Experience | service | A service used for scheduling recurring services and events.  mainly used for managing field services within the activities table | https://github.com/methodcrm/ms-scheduler-api | True |  |
| ms-search-api | Admin | service |  | https://github.com/methodcrm/ms-search-api | True | method-microservices-search- |
| ms-support-agent | Admin |  |  |  | True | method-microservices-supportagent- |
| ms-support-api | Admin | service |  | https://github.com/methodcrm/ms-support-api | True | method-microservices-support- |
| ms-synclog-api | Integrations |  |  |  | True |  |
| ms-sync-util | Integrations | Service | Used for sync-related front-end calls (initiate sync, get sync information, conflict resolutions) |  | True |  |
| ms-tablesfields-api | Admin | service |  | https://github.com/methodcrm/ms-tables-fields-api | True | method-microservices-tablesfields- |
| ms-tags-api | Vertical App Experience | service | service used by the tags component for tagging management for entities such as customers and contacts on runtime screens | https://github.com/methodcrm/ms-tags-api | True |  |
| new-import-api | Admin |  |  |  | True | method-microservices-import- |
| new-import-stack | Admin |  |  |  | True |  |
| new-import-subscriber | Admin |  |  |  | True | method-microservices-importsubscriber- |
| portal-signin-ui | Admin | webapp | signin for method portals app | https://github.com/methodcrm/portal-signin-ui | True |  |
| qbdt-syncengine-client | Integrations |  |  |  | True |  |
| qbo-sync-agent | Integrations |  |  |  | True |  |
| qbo-sync-api | Integrations |  |  |  | True |  |
| qbo-sync-consumers | Integrations |  |  |  | True |  |
| qbo-webhooks-consumer | Integrations |  |  |  | True |  |
| qbo-webhooks-publisher | Integrations |  |  |  | True |  |
| qbo-webhooks-queuecloner-api | Integrations |  |  |  | True |  |
| runtime-core-api | Vertical App Experience |  |  |  | True | method-runtime-api |
| runtime-core-subscriber-api | CRM Experience |  |  |  | True |  |
| runtime-stack | Impact |  |  |  | True |  |
| serverless-computing-analytics | Growth | worker | background code used by aws serverless lambda, to process our AWS SQS Queue of analytics to send to segment. Segment then sounds to all downstream analytic providers. | https://github.com/methodcrm/serverless-computing-analytics | True | method-lambda-serverless-computing-analytics- |
| syncapi-queue-consumer | Integrations |  |  |  | True |  |
| sync-api-xero | Integrations |  |  |  | True |  |
| sync-cronscheduler-xero | Integrations |  |  |  | True |  |
| sync-subscriber-xero | Integrations |  |  |  | True |  |
| unsubscribe | Transactions |  |  |  | True |  |
| Zapier-V2 | Integrations |  |  |  | True |  |

---

## 7. Notes / caveats

* **Sensitive values — scrubbed in this copy.** `ReleaseTeam.TeamSlackAlertChannel`
  contains **live Slack incoming-webhook URLs** (secrets). They have been
  **redacted** here (`[redacted-live-webhook …]`) so this file is safe to commit.
  `TeamCharter` retains raw HTML `<a href>` markup pointing at the (internal,
  non-secret) team-charter Google Doc. The triage routine never needs the
  webhooks — it identifies the owning team by name and notes the team's channel /
  usergroup for reference only, and never posts to either (see Hard rule #13).
* **`loggingId`** on projects is a free-text field (max 1024 chars) used to tie a
  project/area to its logging identifier.
* To get the other saved views (Inactive / All / Unassigned), swap the WHERE
  clause per the table in section 3.
* To pull **live prod** data instead of the local snapshot, run the same SQL
  against the prod AlocetSystem SQL instance (read-only) — the queries are
  identical.
