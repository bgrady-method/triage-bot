Template:

---

**Incident/Alert:**

**Prepared by (Author):**

**Duration:**

**Summary:** 

**Impact:**  

**Root Cause:** 

**Action Items:**  

---

**Incident/Alert:** Thousands of `System.Net.WebException — The remote name could not be resolved: 'microservices.method.int'` errors across the Windows production fleet. 

**Prepared by (Author):** A. Pakbaz

**Duration:** 2026-05-20, \~16:00 EST → \~16:30 EST (≈ 30 minutes)

**Summary:** All 11 Windows EC2 instances in production (MSN01/02, PROD-CLASSIC-01/02, PROD-NEW5/6, PROD-REPORT-03/04, PROD-UTILITY-01/02/03) intermittently failed to resolve any name in the Route 53 private hosted zone `method.int` for roughly 30 minutes. The Linux fleet was unaffected. The dominant failing name was `microservices.method.int` (the internal microservices LB), which most application code paths hit. Resolution recovered without manual intervention as the bursts subsided and the DCs' negative DNS cache expired.

**Impact:**

* Windows-hosted services that call internal microservices via `*.method.int` returned 5xx / unhandled exceptions for the duration. Most visible in the report-generation API (`PROD-REPORT-03/04`), classic API (`PROD-CLASSIC-01/02`), and microservices nodes (`MSN01/02`). User-facing impact: report generation, secure document links, and any cross-service API call that went out through `microservices.method.int` failed.
* Linux fleet: no impact. had a pre-existing systemd-resolved bypass that sends `*.method.int` directly to `169.254.169.253` from its own ENI, so it didn't share the DC bottleneck. Other Linux hosts were not on the hot path during the burst.
* Domain controllers `prod-dc-01` and `prod-dc-02` stayed up; AD authentication and `method.local` resolution were unaffected.
* Method was flaky and screens and UI was not accessible or taking too long to load.

**Root Cause:** Every Windows EC2 instance forwards DNS to the two domain controllers, and both DCs forwarded `*.method.int` queries to the AWS Route 53 Resolver at `172.31.0.2`. That destination counts against the AWS per-ENI **1024 PPS link-local quota** (also covers `169.254.169.253`, IMDS, NTP, Windows Licensing). The combined query rate from the 11 Windows hosts pushed the DCs' link-local PPS over the cap during a burst; AWS silently dropped the excess packets at the VPC fabric. The DCs' conditional forwarder for `method.int` had `UseRecursion=True`, so on forwarder timeout the DC fell back to root-hint recursion. Root hints cannot resolve `.int` (it's a reserved TLD with no public `method.int` zone), so they returned NXDOMAIN — which the DC then **negatively cached**, extending the visible outage well past the actual packet-drop bursts. ENA `PPS allowance exceeded` counters confirmed shaping events on both DCs; CloudWatch `NetworkPacketsOut` on `prod-dc-01` doubled (1,557 → 2,982) at incident time.

**Action Items:**

| # | Action | Status |
| --- | --- | --- |
| 1 | Provision Route 53 Resolver inbound endpoint in `vpc-18e2127d` (HA pair, 2 IPs). | Done — `rslvr-in-33bec0891b854ea8b` IPs `172.31.223.154`, `172.31.168.212`, OPERATIONAL. |
| 2 | Pilot the new path on `methodmega.int` and `methodbeta.int` (dev zones). | Done — verified on `dev-mega-windows` and `dev-mega-linux`. |
| 3 | Migrate `method.int` conditional forwarder on both DCs from `172.31.0.2` → endpoint IPs; set `UseRecursion=$false`. | Done — verified on 5 Windows + 6 Linux prod hosts post-change. |
| 4 | Remove the systemd-resolved `~method.int` override from the 9 Linux hosts that had it (`prod-rt-01..04`, `prod-rt-worker-01/02`, `prod-msl-03/04/05`); confirm DC path resolves. | Done — all 9 verified resolving via DC → endpoint. Backups at `/etc/systemd/resolved.conf.bak.20260521-*`. |

---

**Incident/Alert:** MongoDB `rs01` Production Crash — File Descriptor Exhaustion

**Prepared by (Author):** Arash Pakbaz

**Duration:** 2026-05-15 13:38 UTC → 15:09 UTC (\~91 minutes)

**Summary:**  
The primary MongoDB node (`rs01`) self-aborted after hitting its 64,000 open file descriptor limit. The replica set failed over in \~10 seconds but `rs01` stayed down for 91 minutes due to no auto-restart configuration, leaving all traffic on a single data node and causing customization screens to be slow.

**Impact:**

* Customization affected for \~91 minutes (elevated latency); \~10 seconds of complete write unavailability during failover.
* No data loss or corruption.
* `rs02` (current primary) is at \~27,300/64,000 FDs and rising — at risk of the same crash.

**Root Cause:**  
`LimitNOFILE=64000` in `mongod.service` (never overridden from the install default) was too low for the multi-tenant, one-DB-per-tenant deployment. Migration 716 (commit `23a3164`) created two new collections in every tenant database, pushing FD count past the limit. WiredTiger returned `errno 24 (EMFILE)`, triggering fatal assertion 50882 and a self-abort. The 91-minute duration was caused by the absence of `Restart=on-failure` in the service unit. The migration was written correctly — it exposed a pre-existing infrastructure misconfiguration.

**Action Items:**

| Priority | Action |
| --- | --- |
| **Immediate** | Raise `LimitNOFILE=infinity` and add `Restart=on-failure` via systemd drop-in on all three replica set members (rs01 first, then step down rs02). |

---

## Incident/Alert:

DNS Resolution Failures Causing “Host Unknown” Errors for `microservices.method.int`

## Prepared by (Author):

Arash Pakbaz

## Duration:

First observed May 14, 2026 – ongoing intermittent occurrences (Windows DNS negative caching persists for 15 minutes per event)

## Summary:

Windows servers intermittently fail to resolve the private DNS record for `microservices.method.int` due to excessive DNS queries from a Windows machine causing Route53 throttling. When throttled, Route53 returns `NXDOMAIN`, which Windows caches for 15 minutes, resulting in recurring “Name or service not known” errors.

## Impact:

Production services intermittently fail to resolve `microservices.method.int`, causing degraded functionality or temporary outages during the negative DNS cache window. Issue classified as Very High Impact.

## Root Cause:

Route53 throttles DNS traffic when an instance exceeds 1024 packets per second, returning `NXDOMAIN`. Windows DNS clients cache the negative response for 15 minutes. Contributing factors include excessive DNS queries from a Windows machine and limited DNS client logging visibility.

## Action Items:

**Immediate:** Enable DNS client logging on all Windows servers; configure Datadog to collect throttling metrics (`bw_in_allowance_exceeded`, `bw_out_allowance_exceeded`, `pps_allowance_exceeded`, `conntrack_allowance_exceeded`, `linklocal_allowance_exceeded`).  
**Medium-Term:** Reduce Windows DNS `MaxNegativeTtl` from 15 minutes to 30 seconds.  
**Long-Term:** Evaluate Route53 Resolver inbound endpoint; expand conditional forwarding strategy across Windows clients.

---

**Incident/Alert:** Google Calendar Sync failed deployment

**Prepared by (Author):** <custom data-type="mention" data-id="id-0">@Michael Griffiths</custom> 

**Duration:** 8:54am to 9:08am May, 6, 2026

**Summary:** Upon deployment of Calendar Sync, it failed, health check.  Wasn’t able to run.

**Impact:**  Calendar Sync would have been delayed for any users during this period, until the roll back \~ 20 mins.

**Root Cause:** Project was upgraded to use .NET 4.8, unfortunately the server didn’t have this version of .Net installed.

**Action Items:**  Verify any .NET upgrades with Devops first, to ensure the targeted Framework is installed and there will be no failures on deployment.

---

**Incident/Alert:** Classic UI on classic machines stopped working at 8:01 AM (5 minutes) and 9:39 AM (3 minutes), and also intermittently showed signs of slowness during the day.

**Prepared by (Author):** Matt Pourasadi

**Duration:** May 4, 2026 incidents at 8:01–8:06 AM and 9:39–9:42 AM, along with a few intermittent short-lived slowness reports.

**Summary:** Classic UI app pools crashed a few times during the day and needed to be restarted. We reduced EDA load and later redeployed the previous code.

**Impact:**  Classic UI became unresponsive for a few minutes for all customers during the incidents, and users also experienced intermittent slowness throughout the day.

**Root Cause:** We did not have any clear errors pointing to a specific issue, only app pool crashes reported in Event Viewer.

Over the past few days, we had similar incidents on both Classic and QBO machines, so initially we suspected Datadog tracer or older MassTransit libraries. As a mitigation step, we disabled the Datadog tracer. We had also performed a major Datadog tracer upgrade on the same day, which we thought might have contributed to the issue. At the same time, we reduced the number of accounts producing EDA events, and the issue effectively disappeared afterward.

At this point, we believe the issue may be related to the new EDA NuGet package upgrade deployed the day before. Under high load, the new asynchronous calls may have caused thread starvation in older .NET Framework/classic code paths, which is a known limitation in older frameworks according to AI-assisted analysis.

Matt created a branch using a modified NuGet package without asynchronous calls and tested it under heavy load in Warehouse, simulating around 1,000 requests against classic-ui with 36 parallel threads. During testing, the synchronous version, although producing around 62 timeouts out of 1,000 requests, never crashed. However, the asynchronous version consistently crashed after around 500–600 calls and returned 502 errors.

This may explain why the latest release triggered the issue. However, the earlier Classic incidents from previous days may still have been related to Datadog tracer, older MassTransit libraries, or a combination of these factors amplifying each other.

**Action Items:**  We redeployed the previous stable code on the same night as the incident. The new NuGet package version without asynchronous calls is ready, but we postponed deployment until we observe more stability on the Classic machines.

---

**Incident/Alert:** QuickBooks Desktop sync was down, along with Accounting View Deltas Regeneration Response Not Successful, meaning also new account creation was down.

**Prepared by (Author):** <custom data-type="mention" data-id="id-1">@Michael Griffiths</custom> 

**Duration:** May 4, 2026 8:50am - 9:20am

**Summary:** Multiple issues:

* QuickBooks Desktop sync was failing.   
* Accounting View Deltas Regeneration Response Not Successful
* Above accounting view deltas also caused account creation failure

**Impact:** QBDT customers (all, but after reverted, background sync would resume, so only down during this time), anyone trying to change a view (a few accounts), and account signup (1 account).

**Root Cause:** Incorrect version of legacy-syncservice-api was deployed.  Was believed this prior version didn’t have Devops code changes, where it unfortunately already had it in it, and the newer version had a fix to the issue.

**Action Items:** Going forward, if a version is found to be defective, then any fix, would cause that entire project to have to run through regression again.

---

**Incident/Alert:** Real Time Sync (QBO) wasn’t working.

**Prepared by (Author):** <custom data-type="mention" data-id="id-2">@Michael Griffiths</custom> 

**Duration:** April 30, 2026 10:00am - 4:30pm

**Summary:** Real time sync was down during this period for QBO.  Calls being made to QBO Sync, API was not going into rabbit for the consumers to process.  It required us to reset the app pool on Sync (Util 2 & 3) for it to go into queue.  

**Impact:** All QBO customers.

**Root Cause:** Combination of 2 things.  Mass transit is old on this project.  Datadog’s trace caused this blockage in coordination with mass transit, that essentially blocked stuff from going into rabbit.

**Action Items:** Datadog’s trace has been removed now from QBO Sync.

Follow up actions: Code change was made by Arash to help prevent this for when we want to put Datadog’s trace back on.

During AI Upgrade - we are looking at updating Mass Transit to a more modern in date version, for QBO Sync.

---

**Incident/Alert:** Platform Slowness — Redis Keyspace Scan Spikes

**Prepared by (Author):** Arash Pakbaz

**Duration:** April 28, 2026 — Three separate events throughout the day:

* 9:30 AM 
* 11:00 AM
* 1:00 PM 

**Summary:** The platform experienced three separate episodes of sporadic slowness on April 28, 2026, each correlating with Redis CPU/latency spikes. All three events were caused by the cache-clear flow executing broad keyspace pattern scans (`SCAN` commands) against Redis when processing high volumes of cache invalidation messages. Under load, these scans competed for Redis resources across shards, degrading response times for all customers.

**Impact:** All customers experienced sporadic platform slowness during each spike window. The impact was broad but intermittent, consistent with Redis saturation under burst cache-clear activity. No data loss or data integrity issues were identified.

**Root Cause:** The `CacheClearEventConsumer` was clearing cache entries by pattern matching (e.g., `UserContext:account:identity*`, `PreferenceContext:account:identity*`). On Redis/Valkey, pattern deletes require scanning the full keyspace to locate matching keys. Under high cache invalidation rates — such as coordinated user or permission changes — this generated a large volume of `SCAN` commands across multiple shards simultaneously, causing Redis to spike and API response times to degrade. Additionally, duplicate cache-clear messages for the same account/identity were not coalesced, meaning the same expensive scan could execute many times in rapid succession for the same scope.

**Action Items:**

<custom data-type="smartlink" data-id="id-3">https://method.atlassian.net/browse/PL-62474</custom> 

1. **Deploy tag-based cache clears** — Replace pattern-scan deletes with tag-based deletes for `UserContext` and `PreferenceContext` cache groups. Cache writes will maintain Redis Set tags (e.g., `CacheTag:tag:usercontext:acme:identity`), and clears will scan only the small tag set rather than the full keyspace.
2. **Enable coalescing for cache-clear messages** — Implement coalescing so that burst duplicate messages for the same `cacheGroup + account + identity` scope collapse into a single active clear (with at most one replay), preventing the same Redis scan from executing dozens of times under burst conditions.
3. **Enable legacy pattern fallback flag for rollout** — Set `CachingOptions.RunLegacyCacheClearPatternFallback: true` during rollout to ensure old untagged keys (written before the tag-based changes are deployed) are still cleared. Once old keys have expired naturally and all instances are running tag-aware code, set the flag to `false` to fully eliminate keyspace scans.
4. **Add observability for legacy fallback usage** — Confirm structured log entries are emitted when the legacy pattern fallback branch executes, to provide a direct signal in production that old-style scans are still running and measure progress toward full tag adoption.
5. **Flush untagged Redis keys post-deploy** — After full deployment and validation, flush all existing `runtime-core` Redis keys in production so that all subsequently written keys carry tags and the fallback can be safely disabled.
6. **Set up Redis alerting** — Add monitoring alerts for Redis `SCAN` command rate and keyspace-scan latency to detect future regressions before they cause customer impact.  

---

**Incident/Alert:**<custom data-type="smartlink" data-id="id-4">https://method.atlassian.net/browse/PL-62491</custom> 

**Prepared by (Author):** <custom data-type="mention" data-id="id-5">@Michael Griffiths</custom> 

**Duration:** Apr 27, 2026 10am - Apr 28, 2026 - 4pm  \~ 30hrs

**Summary:** Some customers had issues with (Gmail) Method side bar - with a message of Bandwidth quota exceeded.  This incident was due to Google themselves.  They are the ones that fixed the issue as well.  They didn’t provide many details, but this appears to have been happening to others previously as well.  Mostly around authentication discovery pages and calls to said pages.  Should be noted, that while ticket on Google has marked fixed, others are still saying it’s not for them.  For our tests, it appears to have fixed issues that Method had.  Google’s issue tracker/ticket can be found here: <custom data-type="smartlink" data-id="id-6">https://issuetracker.google.com/u/0/issues/505172128?pli=1</custom> 

**Impact:** Could have happened to any users using our sidebar, however, it appears to be a handful of customers and many method internal users that were testing.

**Root Cause:** Google’s issue.

**Action Items:** Nothing from our side.

---

**Incident/Alert:** <custom data-type="smartlink" data-id="id-7">https://method.atlassian.net/browse/PL-62423</custom> 

**Prepared by (Author):** San Oo

**Duration:** 10:18 - 10:45

**Summary:** Multiple customers reported on Sunday that subscription pages are not responding. Browser console showed 500 error. We rolled back biilingengine-api Friday release to resolve the issue.

**Impact:** Method:New customers

**Root Cause:** The team was unaware that billingengine-api initially supported two API keys. During recent refactoring, AI removed one key (key1). The subscription page uses key2, which worked during regression testing. However, on Saturday morning, the nightly billing agent failed because it used key1. We replaced key1 with key2 in production to rerun billing, which caused the subscription page to stop working.

**Action Items:** 

* Establish procedure to identify dependencies and include them in testing
* Expand regression test coverage to catch similar issues
* Avoid planning billing-related releases on Friday because billing runs at night and issues may surface only in the morning

**Incident/Alert:** Method was down during morning release (PL-62401)

**Prepared by (Author):** San Oo

**Duration:** 9:20 AM - 10:53 AM

**Summary:** During the morning release, some customers couldn’t sign in, and others who were already signed in, saw errors on loading screens.

**Impact:** Method was down for all customers

**Root Cause:** Release dependency issue — while fixing the ms-preferences-api endpoints with weak security checks, the team added security tags like `[AllowInternal]` and `[AllowIdentity]` to block external access. Upstream services were updated to call the internal routes instead of the public ones. There are 9 services that depend on ms-preferences-api. After ms-preferences-api was released, the other services were still mid‑release, which caused their calls to be rejected and the system to stop working.

**Action Items:** 

* Morning releases were rolled back to restore service.
* Avoid dependency-heavy releases where possible; use a safer release strategy.
* All teams have been reminded that multi‑dependency releases must be reviewed by DevOps and Leads.
* High‑risk releases should be done outside business hours to minimize impact.


**Incident/Alert:** SendGrid OpsSubUser Suspension — Method Transactional Email Delivery Blocked (tanamcmullan .com / fmpublicationsltd).

**Prepared by (Author):** _Hammad Ali Hashmi_

**Duration:** April 21, 2026 \~10:51 PM EDT (SendGrid blocked OpsSubUser) → April 22, 2026 \~8:59 AM EDT (transactional email delivery restored platform-wide via sub-user reroute). Offending account fully sanitized and email capability re-enabled later the same day after owner identity verification.

**Summary:**  
Twilio SendGrid suspended our OpsSubUser account after detecting phishing activity associated with `tanamcmullan .com`. Transactional emails routed through OpsSubUser were blocked until outbound traffic was rerouted to an alternate sub-user the following morning. The offending tenant was identified as the Method account `fmpublicationsltd` - a paid, subscriber since 2022. The offending sender was a leftover attacker-created user (`METHODE`) from the earlier Tunisia incident on the same account, never cleaned up. The stale user was disabled, a stale API key from the Tunisia window was deleted, marketing and transactional email was disabled on the account, the owner's session and password were invalidated, and SendGrid was asked to reinstate OpsSubUser with full remediation evidence.

**Impact:**

* Transactional emails routed through OpsSubUser could not be delivered until traffic was rerouted. Customers with their own authenticated custom domains or private email servers were not impacted. Sends attempted during the affected window were deferred rather than lost.
* Method account `fmpublicationsltd` was used as a phishing delivery vehicle for approximately 28 days

**Root Cause:** 

* The admin team did not fully clean up the compromised account during the prior Tunisia incident, leaving attacker-created user accounts active on the platform. Those accounts were later used as spammers in this incident. Specifically, one user (`METHODE`) and a stale API key from the Tunisia window remained in place and bypassed the subsequent password reset and 2FA entirely; the `METHODE` user was the sender of every phishing email in this incident.
* Method's platform lacks outbound email content inspection.
* No anomaly detection fires when attacker-style changes are made on an established account (new users added, API keys created, owner email changed to a non-matching domain).

**Action Items:**

**Completed:**

* Identified the offending account `fmpublicationsltd` via MongoDB lookup on the reported phishing URL and confirmed against S3 email backups.
* Deactivated the attacker-leftover `METHODE` user and the owner admin (temporarily, pending identity verification).
* Force-expired sessions, triggered password reset, and deleted the stale Tunisia-era API key.
* Disabled marketing and transactional email capability on the account; re-enabled later the same day after the owner completed a password change and confirmed 2FA.
* Rerouted outbound transactional traffic from OpsSubUser to an alternate SendGrid sub-user via API key swap and subscriber restart.
* Rotated the OpsSubUser API key with SendGrid and submitted a remediation response requesting reinstatement.

**Planned:**

* Prevention, detection, and response improvements continue to be tracked under epic [PL-61115](https://method.atlassian.net/browse/PL-61115). [PL-62271](https://method.atlassian.net/browse/PL-62271) is the interim ticket scoping outbound email content screening for new accounts.
* [PL-62308](https://method.atlassian.net/browse/PL-62308) is the hotfix in flight — Claude-based detection with a per-email hold and admin release/drop endpoints — to reduce exposure while the interim and epic work are completed.

**Incident/Alert:** Issue causing some saves in method from syncing to QuickBooks/Xero.

**Prepared by (Author):** _Michael Griffiths_

**Duration:** April 17, 2026 9:00 AM EDT – April 17, 2026 \~5:00 PM EDT (some of the saves)

**Summary:**  
Code snippet would sometimes cause ServerTimeModified to not get updated to latest date, which would cause these specific records from syncing to QuickBooks.

**Impact:**

* Some transactions saved in Method didn’t get sent to QuickBooks.  Follow up ticket for migration to set these and sync them over.

**Root Cause:** New code introduced to set Xero’s ServerTimeModified back to null after successful sync impacted QB as well.  Sometimes nullifying out ServerTimeModified before it actual synced.  This seemed to be due to a race condition as it only happened intermittently.

**Action Items:**

**Completed:**

* Rolled offending code back no more incidents

**Planned:**

* Follow up migration to set ServertimeModified and pushing these to QuickBooks for records that we can determine were missed.

**Incident/Alert:** SendGrid OpsSubUser Suspension — Method Transactional Email Delivery Blocked (ranksizexxl.club)

**Prepared by (Author):** _Hammad Ali Hashmi_

**Duration:** April 14, 2026 11:10 PM EDT – April 15, 2026 \~10:30 AM EDT (service restored via rerouting to SubUser2; OpsSubUser reinstatement by SendGrid pending)

**Summary:**  
Twilio SendGrid suspended our OpsSubUser account (`ops@method.me`) after detecting phishing activity associated with the domain `ranksizexxl.club`. OpsSubUser handles fallback transactional email delivery for Method customers without authenticated domains, so the suspension blocked transactional emails routed through OpsSubUser until outbound traffic was rerouted to SubUser2 as a temporary mitigation. The offending tenant was identified as the Method account `wanddgital`. The OpsSubUser API key was rotated, the sub-account password was reset, and a remediation response was submitted to SendGrid requesting reinstatement.

**Impact:**

* Transactional emails routed through OpsSubUser could not be delivered until traffic was rerouted to SubUser2.
* Customers with their own authenticated custom domains or private email servers were not impacted.
* Sends attempted during the affected window were deferred rather than lost.

**Root Cause:**

* Method's platform lacks outbound email content inspection. Phishing URLs and suspicious payloads are not scanned or blocked before emails are handed off to SendGrid.
* There is no tenant rate limiting or reputation check for new sign-ups — the account was created and began sending phishing emails within the same day.

**Action Items:**

**Completed:**

* Identified and disabled the malicious tenant account (`wanddgital`)
* Rerouted outbound traffic from OpsSubUser to SubUser2 as interim mitigation
* Rotated the OpsSubUser SendGrid API key and reset the sub-account password
* Deactivated the MethodId and users associated with the account
* Remediation response sent to SendGrid requesting reinstatement of OpsSubUser

**Planned:**

* Prevention, detection, and response improvements are being tracked under epic [PL-61115](https://method.atlassian.net/browse/PL-61115), covering outbound payload inspection, tenant rate limiting for new sign-ups, stricter domain validation, monitoring and escalation, and dynamic sub-user / IP management.
* In parallel, quick-win platform-level improvements — including email body scanning before handoff to SendGrid — are being scoped as interim bandaid fixes to reduce exposure while the epic is being groomed. Tickets will be finalized shortly.

**Incident/Alert:** Elasticsearch Cluster Outage — No Master / All Writes Failed

**Prepared by (Author):** _Arash Pakbaz_

**Duration:** April 13, 2026 — 06:49 UTC to 12:24 UTC _(5 hours 35 minutes)_

**Summary:**  
Two of three Elasticsearch cluster nodes crashed due to native out-of-memory errors, leaving the cluster without a master and blocking all read/write operations. Node 3 (`prod-elasticsearch-audittrail-03`) had crashed approximately 21 hours earlier on April 12 at 09:31 UTC but went undetected as no application-level monitoring was in place. When Node 2 subsequently crashed on April 13 at 06:49 UTC, the cluster lost quorum and became fully unavailable. Both nodes were manually restarted at approximately 12:23–12:30 UTC, restoring cluster health.

**Impact:**  
All services relying on Elasticsearch for audit trail logging were unable to write. Failed events were queued in RabbitMQ with `cluster_block_exception: no master`. No data was lost; queued events were re-processed after the cluster was restored.

**Root Cause:**  
Each node has 30 GB of RAM with no swap. The JVM is configured with 16 GB heap plus 8 GB direct memory, leaving only \~6 GB for the operating system, kernel, and Lucene memory-mapped segment files. During a period of elevated background merge activity, the remaining native memory was exhausted on both nodes, triggering a fatal `mmap` allocation failure (`ENOMEM`). Because the Elasticsearch systemd unit was configured with `Restart=no` (default), crashed nodes did not auto-recover. The absence of port-level monitoring meant Node 3's crash went undetected for over 27 hours.

**Action Items:**

| # | Action | Owner | Status |
| --- | --- | --- | --- |
| 1 | Enable systemd `Restart=on-failure` on all 3 nodes | Ops | ✅ Done |
| 2 | Add Centreon monitoring: ES port 9200 TCP check on all nodes | Ops | ✅ Done |
| 3 | Add Centreon monitoring: Cluster health status check (GREEN/YELLOW/RED) | Ops | ✅ Done |
| 4 | Reduce JVM heap from 16 GB to 12 GB and remove or reduce `MaxDirectMemorySize` to free native memory headroom | Ops | Pending |
| 5 | Add emergency swap (2–4 GB) with `vm.swappiness=1` on all nodes | Ops | Pending |
| 6 | Reduce total shard count (currently 14,248) to below 3,000 via index lifecycle management | Ops | Pending |

‌

**Incident/Alert:**

Field Crew app not accessible to users due to an empty state overlay appearing. 

**Prepared by (Author):**

<custom data-type="mention" data-id="id-8">@Kevin Mistry</custom> 

**Duration:** 

\~20 mins

**Summary:**

Customers reported an empty state overlay is stopping them from accessing the Field Crew app. It is behind a release feature flag which was turned off immediately unblocking customers.

**Impact:**

Customers were not able to see their assigned work orders as reported for two accounts.

**Root Cause:** 

The condition to dismiss the overlay was based on a feature which creates visits as soon as a work order is created for the technician it is assigned to. However this feature was newly introduced and not applicable for older accounts resulting in overlay not getting dismissed. 

**Action Items:**

Switch off feature flag as immediate fix. Adding right condition to dismiss overlay for field crew to check for user’s access to work orders

‌

**Incident/Alert:**  
Connection issue for QBDT Real-Time Sync (PL-61643) – Real-Time Sync from Method → QuickBooks Desktop not triggering as expected for some instances

**Prepared by (Author):**  
Arash Pakbaz

**Duration:**  
Incident observed on 2026-03-13. Symptoms persisted until DNS routing was corrected by temporarily adding a host entry on `prod-classic-1` and `prod-classic-2`, followed by a permanent fix updating the target group to point to the correct machine (`prod-utility`).

**Summary:**  
Customers reported that Real-Time Sync from Method to QuickBooks Desktop (QBDT) was not working as expected. Some QBDT instances showed as “connected”, but Real-Time Sync events were not triggering. Background, full, and changes syncs continued to behave normally.

Investigation showed that the DNS configuration for `legacy-sync-services` running on `prod-classic-1` and `prod-classic-2` was misrouted: DNS pointed to a load balancer whose target group routed traffic to an incorrect machine. This caused connection attempts to either time out or fail, resulting in Real-Time Sync failures for affected customers.

A temporary fix was applied by adding a specific host entry on `prod-classic-1` and `prod-classic-2` to force traffic directly to the correct IP. A permanent fix was then implemented by adding the correct machine (`prod-utility`) to the load balancer’s target group so that DNS-based routing works correctly. The temporary host entries will be removed once confirmed stable.

**Impact:**

* Real-Time Sync from Method → QBDT failed for some customers.
* Some customer instances appeared “connected” but did not receive/trigger Real-Time Sync events.
* Immediate-change visibility in QBDT was degraded for impacted customers.
* Full/changes/background sync behavior remained unaffected, so data integrity and eventual consistency were preserved, but with reduced timeliness for Real-Time updates.
* Error observed:  
  `A connection attempt failed because the connected party did not properly respond after a period of time, or established connection failed because connected host has failed to respond`

**Root Cause:**

* The DNS configuration for `legacy-sync-services` on `prod-classic-1` and `prod-classic-2` resolved to a load balancer whose target group was incorrectly configured.
* The target group pointed to the wrong machine, so Real-Time Sync traffic was not reaching the correct service endpoint.
* As a result, connection attempts from Real-Time Sync to the intended backend were timing out or failing, causing Real-Time Sync events not to be processed.

**Action Items:**

1. **Immediate / Completed**

    * Add temporary host entries on `prod-classic-1` and `prod-classic-2` to route directly to the correct sync endpoint:
    
        ```
        172.31.15.210 sync-tcpip.methodintegration.com  
        ```
    * Update the load balancer’s target group to include the correct machine (`prod-utility`) so that DNS resolves to a correctly routed path for `legacy-sync-services`.
    
2. **Follow-Up / Permanent Hardening**

    * Remove temporary host entries on `prod-classic-1` and `prod-classic-2` after validating that DNS and load balancer routing are working correctly in production.
    * Add monitoring/alerts for:
    
        * Health of `legacy-sync-services` endpoints behind the load balancer.
        * Real-Time Sync error rates specifically for QBDT connections (timeouts / host unreachable).
        
    * Implement configuration validation or deployment checks to ensure load balancer target groups are updated consistently when backend machines or roles change.
    * Document the correct DNS → load balancer → target group → machine mapping for `legacy-sync-services` and QBDT Real-Time Sync, including the role of `prod-utility`.
    * Review recent infrastructure or DNS changes around Real-Time Sync and add a checklist item to verify Real-Time Sync connectivity as part of any relevant change rollout.
    

‌

**Incident/Alert:**

Intermittent Site down / unavailable Error 

**Prepared by (Author):**

Ismael Sagullo

**Duration:** 

21 hours ( Mar 2, 13:30 - Mar 3, 07:30 EST)

**Summary:**

Customers reported intermittently seeing the Method error page, through out the duration of the incident

![](blob:https://media.staging.atl-paas.net/?type=file&localId=7633ecba5a1b&id=b2307943-8007-48d8-8b60-529ceb84e13d&&collection=contentId-133496969&height=1158&occurrenceKey=null&width=1680&__contextId=null&__displayType=null&__external=false&__fileMimeType=null&__fileName=null&__fileSize=null&__mediaTraceId=null&url=null)
**Impact:**

Refreshing the browser allowed users to continue on past the error.

**Root Cause:** 

* The error was only appearing on the server prod-new-04. it was recently created to help with load during releases.
* The specific error

    * “Login failed. The login is from an untrusted domain and cannot be used with Integrated authentication.” when trying to connect to the SQL server
    * was generated from “method-platform-ui”
    
* The login failure was caused by an incorrect password used by service account that runs the IIS app pools on the server (prod_new_gmsa$)
* the default password rotation for the group managed service account is 30 days, which is approximately when the new server was created.
* once the password changed the service account could not authenticate with the SQL server
* The service account could not obtain the new password because it was not a member of the Active directory group that provided access to the new password

**Action Items:**

* the immediate fix was to remove prod-new-04 from the target groups / load balancer so that it was no longer accessible from the internet
* the permanent fix was to add the server to the Active directory group “prod_new_gmsa” so it would have the required permissions to access the password when it changes
* monitoring / health checks were configured in Centreon for the endpoints hosted on the server  

**Incident/Alert:**

Customer & Leads App | The “Activities Open” App Ribbon is missing from the View Contact screen

**Prepared by (Author):**

Swaroop Nayak

**Duration:** 

4 hours (9am - 2pm)

**Summary:**

On February 12th, 2026, we released a new feature that included app ribbon visibility settings as part of an app update.

On February 17, 2026, the Customers and Leads app was published. During this publish, the visibility for one of the app ribbons was inadvertently set to hidden. This change was shipped out to all accounts, resulting in the **Activities Open** tab being hidden on the View Contacts page when the entity type is Customer.

**Impact:** 

All clients opted in for the update to the Customers and Leads app were affected by this issue.

**Root Cause:** 

The issue was caused by a **manual configuration error during app publish**.  
While publishing the Customers and Leads app, the visibility setting for the **Activities Open** app ribbon was inadvertently set to **hidden** for the **Customer** entity type.

This change was not caught before publish and, due to the new App Ribbon visibility feature released on **February 12, 2026**, the incorrect configuration was included in the app update and shipped to all accounts.

There was **no tooling or platform defect** involved; this was a **human error during configuration**.

**Action Items:**

**Completed:**

* Ran a migration to set the **Activities Open** app ribbon visibility to `true` for all affected accounts

    * <custom data-type="smartlink" data-id="id-9">https://method.atlassian.net/browse/PL-61114</custom> 
    

**Process Clarification:**

* A migration is **not required** to fix this type of issue.
* The correct and preferred approach is:

    * Toggle the App Ribbon visibility via the UI
    * Re-publish the screen and the app to ship the corrected configuration to all accounts
    
* This process is documented in the linked Tech Story (includes video walkthrough).

    * <custom data-type="smartlink" data-id="id-10">https://method.atlassian.net/browse/PL-54962</custom> 
    

**Preventative Measures:**

* Add **QA automation coverage** for stock apps to validate App Ribbon visibility configurations before release. <custom data-type="smartlink" data-id="id-11">https://method.atlassian.net/browse/PL-61157</custom> 
* Introduce a **pre-publish checklist** item to explicitly verify App Ribbon visibility settings for all entity types.
* Ensure App Ribbon visibility changes are **explicitly reviewed** as part of the app publish process.

‌

**Incident/Alert:**

SendGrid Sub-User 2 Suspension — Method Fallback Email Delivery Blocked

**Prepared by (Author):**

Richard Pangborn

**Duration:** 

\~6 days (February 11, 2:19 PM – February 17, 3:29 PM)

**Summary:**

On February 11, 2026 at 2:19 PM, SendGrid suspended our sub-user 2 account (sub-account 43133395) after detecting phishing activity originating from a malicious tenant. Sub-user 2 handles fallback email delivery for all Method customers who do not have an authenticated custom domain, routing both marketing and transactional emails through [mail.method.me](http://mail.method.me).

The suspension went unnoticed until February 13 at 2:07 PM, when customers began reporting email campaigns stuck in “Pending” status. Investigation by the CRM Experience, Transactions, and DevOps teams identified the sub-user suspension as the root cause. The offending account (statewidehireptyltd) was disabled and shut down the same evening.

A support ticket was submitted to SendGrid on February 13; however, due to Method’s Basic (free) support plan, response times were slow and initial replies were generic. SendGrid’s Fraud Ops team eventually acknowledged the phishing activity and required several non-negotiable security remediation steps before reactivation: deletion of the old API key, rotation of the sub-account password, and enabling two-factor authentication.

Arash Pakbaz (Architecture/DevOps Manager) completed all remediation steps on February 17 at approximately 1:10 AM. SendGrid confirmed reactivation at 1:15 AM. Full service was verified when a duplicate campaign was successfully delivered at 3:29 PM on February 17.

**Impact:**

* All customers without authenticated custom domains were affected. Marketing and transactional emails routed through sub-user 2 ([mail.method.me](http://mail.method.me) fallback) were blocked from delivery for the duration of the incident.
* Customers with their own authenticated domains or private email servers (SMTP) were not impacted.
* Approximately 1,000 marketing emails were stuck in “Pending” status.
* At least 10 accounts used Email Campaigns during the affected window (Feb 11–17):

| **Account** | **Dates** |
| --- | --- |
| allsportnettingco1  
betterbuychairsinc  
brontebaycpaprofessionalcorporation2  
chalmersford  
cherrywoodpartnersinc  
dealer121  
digitalvideogroup2  
egeproducts  
flipoffice4  
fourpointsplatinum  
gopowertrain2  
gutterguysofmaryland  
homewatchofarizona2  
leddy  
livewallmedia2  
m11andytestaccount  
m11gozdebulut  
maconstructiongroup  
mtaco1  
namesakebrewing  
nspireexperts  
omnivisionhomeservicesllc  
rcmaintenanceandremodelinginc  
saveonlaser  
serigging  
silverbackcommunicationsllcco1  
sitepieces2  
skyproduct  
southgateprocessequipmentinc  
spikeonsitesolutions  
thymeandseasonscateringatriverdalemanor  
wpvc2 | Feb 11,12,13,14,15,16 |

* **Note:** This count reflects only Email Campaign sends. Additional impact from custom app email sends (e.g., digitalvideogroup2 via DVG Events) and transactional emails is not fully quantified but was also affected.
* Some emails that were deferred too long ultimately bounced and had to be manually resent as duplicate campaigns (confirmed for spikeonsitesolutions).

**Related Tickets:**

* [**PL-61099:** Email Campaigns – Emails getting stuck in Pending](https://method.atlassian.net/browse/PL-61099)
* [**PL-61100:** Sent Emails – Emails sent from the custom app are on a Pending Status](https://method.atlassian.net/browse/PL-61100)

**Root Cause:** 

A malicious tenant account (statewidehireptyltd) signed up for Method on approximately January 28, 2026 and abused the platform to dispatch phishing emails. The account sent at least 6 emails, 3 of which contained phishing hyperlinks associated with the domain “<custom data-type="smartlink" data-id="id-12">http://pemulwuyproject.org.au</custom> .” This activity triggered SendGrid’s suspicious activity detection system, which suspended our entire sub-user 2 account on February 11 at 2:19 PM.

The suspension was not detected by Method’s team for approximately 2 days because:

1. The SendGrid suspension notification email was not routed to an actively monitored inbox or alerting channel.
2. There was no automated monitoring or alerting in place to detect when a SendGrid sub-user is suspended.
3. Method’s platform lacked outbound email content inspection to prevent phishing emails from reaching SendGrid in the first place.

Resolution was further delayed by:

1. Method’s Basic (free) SendGrid support plan, which provides only ticket-based support with no guaranteed response times, no phone support, and no priority escalation path.
2. Credential access gaps: the sub-user password was not stored in Passbolt, and the team had to locate access through multiple people before remediation could begin.
3. The incident fell over a long weekend (Family Day), reducing team availability.

**Action Items:**

**Completed:**

* Identified and disabled the malicious tenant account (statewidehireptyltd)
* Rotated the SendGrid sub-user 2 API key
* Reset the sub-account password
* Enabled two-factor authentication (2FA) on the sub-account
* SendGrid reactivated sub-user 2 (confirmed Feb 17, 1:15 AM)
* Verified email delivery restored; affected campaigns resent successfully

**Planned — Cross-Team Discussion Scheduled: Wednesday, February 19, 2026 at 1:00 PM**

The following items require cross-team alignment including Product Management, Tech Leads, and potentially Sales leadership. These will be discussed at the Wednesday Tech Discussion:

_**Prevention (requires PM buy-in):**_

1. **Outbound Payload Inspection:** Implement an asynchronous scanning service to flag phishing signatures or suspicious links before they hit the SendGrid API.

    1. <custom data-type="smartlink" data-id="id-13">https://method.atlassian.net/browse/PL-61122</custom> 
    2. Owner: CRM Experience Team
    3. Assigned: Arash → Phil for Security Guidelines, and Business Requirements
    
2. **Tenant Rate Limiting:** Tighten outbound volume limits for new sign-ups until they’ve cleared a reputation check.

    1. <custom data-type="smartlink" data-id="id-14">https://method.atlassian.net/browse/PL-61123</custom> 
    2. Owner: CRM Experience Team
    3. Team is doing[ a spike investigation here](https://method.atlassian.net/browse/PL-61158) to determine our acceptance criteria for this ticket.
    
3. **Stricter Domain Validation:** Harden the requirements for new accounts to prevent the use of unverified sender addresses.

    1. <custom data-type="smartlink" data-id="id-15">https://method.atlassian.net/browse/PL-61124</custom> 
    2. Owner: CRM Experience Team
    3. Team is doing [a spike investigation here](https://method.atlassian.net/browse/PL-61158) to determine our accpetance criteria for this ticket.
    

_**Detection & Response:**_

1. **Monitoring & Escalation:** Improve alerting so we’re notified immediately if a sub-account is suspended, with a clear escalation path.

    1. SDMs & TLs identified the email notification and are adding Gmail alert tagging to ensure it doesnt get lost or go to spam and remains critical.
    2. CRM experience team will look into <custom data-type="smartlink" data-id="id-16">https://method.atlassian.net/browse/PL-61120</custom> 
    
2. **Runbooks & Access Readiness:** Update the suspension runbook and ensure owners/teams have the right access (including updating Passbolt) so we can respond faster.

    1. CRM Experience team will add this new item to their runbook <custom data-type="smartlink" data-id="id-17">https://method.atlassian.net/browse/PL-61125</custom> 
    2. they will also move over transactions runbooks items in confluence to theirs
    3. Arash is working to ensure we all have sufficent access for the steps <custom data-type="smartlink" data-id="id-18">https://method.atlassian.net/browse/PL-61126</custom> 
    
3. **IP Capacity & Tiering:** Evaluate increasing our verified IP pool / SendGrid tiers, and add a way in our support tools to assign different outbound tiers to trusted clients.

    1. CRM team will action this to ensure we have more subusers & ips and be able to modify this without deployments… so we are less fragile  
      <custom data-type="smartlink" data-id="id-19">https://method.atlassian.net/browse/PL-61159</custom> 
    

_**Vendor Relationship:**_

4. **SendGrid Support Plan Upgrade:** Evaluate upgrading from the current Basic (free) support plan to a paid tier for faster SLA-backed response times. Current options:

    1. update: decided to hold off for now afer discussion, but open to moving this if we get more isntability.
    

| **Plan** | **Cost** | **Response Time** | **Channels** |
| --- | --- | --- | --- |
| Developer (current) | Free | N/A | Ticket only |
| Production | \~$250/mo or 4% of spend | 3–9 business hours | Ticket, Chat |
| Business | \~$1,500/mo or 6% of spend | 1 hour (critical) | 24/7 Phone, Email, Chat |
| Personalized | \~$5,000+/mo or 8%+ of spend | Custom SLA | Dedicated engineer |

The Business plan would have provided 24/7 phone support and a 1-hour critical issue SLA, which could have significantly reduced this incident’s resolution time from \~6 days to potentially under 24 hours.

‌

### **Incident/Alert:**

Multi-Tenant Runtime Pages Access Issue. Several tenant accounts unable to access custom pages with "Call Routine" actions.

**Prepared by (Author):**

Gozde Bulut

**Duration:** 

\~1.5 hours (8:58am - 10:19am)

**Summary:**

On February 9, 2026, we made a change to improve how the system retrieves app names across accounts. This change unintentionally exposed an existing issue where some tenant accounts couldn't properly access their database, causing certain pages (like Invoice List and Sales Receipt List) to fail to load.

**Impact:**

Not all tenants were affected, only those using specific page configurations with "Call Routine" actions on page load/focus.

* **Primary Account:** mobilitycitybocaratonfl (multiple tenant locations)
* **Secondary Account:** JudicialServicesRR (judicialservicescr)

**Root Cause:** 

The app name improvement we made changed how the system looks up app names in the cache. This revealed a hidden problem: some parts of our code were using the wrong account reference when connecting to the database for tenant accounts.

**Action Items:**

**Completed:**

* Rolled back the change to restore service (Ticket <custom data-type="smartlink" data-id="id-20">https://method.atlassian.net/browse/PL-60985</custom> )

**Planned:**

* Adding comprehensive unit tests specifically for multi-tenant GetAppName scenarios to catch this type of issue before deployment
* Automation tests with real multi-tenant account configurations <custom data-type="smartlink" data-id="id-21">https://method.atlassian.net/browse/PL-60992</custom> particularly for the Mobility City account.
* Fixing the underlying GetAppName code issue to ensure tenant accounts always reference the correct main account database

‌

### **Incident/Alert:**

Intermittent failures in **Grid Builder v2** due to incomplete deployment configuration.

### **Prepared by (Author):**

Arash Pakbaz

### **Duration:**

During morning release for about 10-15 minutes

### **Summary:**

Our **Grid Builder v2** service began experiencing intermittent failures, resulting in minor customer impact. Investigation revealed that a new node had been added to the AWS target group; however, the release definition for **App‑Builder** in TFS was not updated to include this new machine. Because of this, deployments were incomplete, and the newly added node did not receive the latest application code. The issue has been resolved by updating the main release definition and preparing all future release definitions accordingly.

### **Impact:**

* **Customer Impact:** Minor intermittent failures experienced by some users of Grid Builder v2.
* **Service Impact:** One node in the target group was running outdated code, causing inconsistent behavior across the environment.

## **Root Cause:**

A new node was added to the AWS target group, but the associated **TFS release definition for App‑Builder** was not updated to include it. As a result, the deployment process did not push updated code to the new node, causing version mismatches across the cluster and leading to intermittent service failures.

### **Action Items:**

### **Completed:**

* Updated the primary TFS release definition to include the new machine.
* Updated all future-ready release definitions to ensure consistency.
* Verified successful deployment across all nodes.
* Validated application stability after the fix.

‌

**Incident/Alert:** Release Instability / IIS Saturation (8:55 AM Release)   

**Prepared by (Author):** <custom data-type="mention" data-id="id-22">@Arash Pakbaz</custom>   

**Duration:** \~45 minutes (8:55 AM – 9:40 AM)   

**Summary:** During the scheduled release at 8:55 AM, the system experienced significant latency and "white screen" freezes. This was caused by a massive spike in 401 errors hitting a specific API endpoint while the environment was in a single-node state due to the deployment rotation. The high volume of .NET exceptions saturated IIS resources, leading to app pool queuing and service degradation.   

**Impact:**

* Users experienced frozen screens and white screens.
* General system unresponsiveness during the deployment window.
* The UI became unusable as the single active node could not process the request volume.
* Increased load due to users manually refreshing their browsers during the lag.

**Root Cause:** 

* A bug triggered a burst of \~1.7k requests to the `GetUtcOffsetFromTimezone` endpoint.
* These requests returned 401 Unauthorized errors.
* `method-ui` was configured to throw .NET exceptions for these errors; in .NET, exceptions are computationally expensive.
* The deployment was mid-rotation, leaving only one node in the Load Balancer.
* The single node's IIS saturated instantly, causing the app pool queue to overflow.

**Action Items:**

* Increased node deployment and deregistration delay by an additional 60 seconds.
* Updated `method-ui` to return response codes directly instead of throwing exceptions.
* Conducted in-depth Athena log analysis to establish WAF rate-limiting thresholds.
* Implementing WAF rules to prevent future request bursts from reaching the app pool.
* Investigating the addition of a "spare" node during the deployment cycle to prevent single-node exhaustion.
* Optimizing the `GetUtcOffsetFromTimezone` endpoint logic to reduce self-inflicted load

‌

**Incident/Alert:** 

TenantId being updated to null during entity updates

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-23">@Hammad Ali Hashmi</custom> 

**Duration:** 

\~7 days (December 22nd - December 29th 2025)

**Summary:** 

A code change deployed on December 22nd (PL-58920) caused entity update operations to set TenantId to null. The issue occurred because the fix for "IndexOutOfRangeException" errors changed the entity retrieval query to only select columns defined in entity metadata. Since TenantId is a system column not included in metadata, it was never retrieved from the database. When the UI performed updates without passing TenantId (expecting it to be preserved from the database read), null values were written back.

**Impact:** 

Entity records across customer accounts had their TenantId set to null during update operations. Any customer performing entity updates during the 7-day window could have been affected, potentially impacting data integrity and multi-tenant isolation.

```
Between 22 - 29 Dec
3 accounts out of 
- 4477 active external accounts
- 4259 total accounts with updates (according to AuditTrail)
~30 records out of 8,197,821 total update operations (according to AuditTrail)
```

**Root Cause:** 

The [PL-58920](https://method.atlassian.net/browse/PL-58920) fix added explicit column selection using metadata fields: .Select(columnNames) where columnNames came from PrimaryTableFields. Since TenantId is a system-level database column not exposed in entity metadata, it was excluded from the query results. The entity was retrieved with TenantId as null, and subsequent updates persisted that null value.

**Action Items:** 

* [PL-59906](https://method.atlassian.net/browse/PL-59906)  - Hotfix deployed to remove explicit column selection and restore original query behavior
* [PL-59920](https://method.atlassian.net/browse/PL-59920)  - Fix DB records which were incorrectly updated with TenantId as null

‌

**Incident/Alert:**

New signups facing onboarding failures

**Prepared by (Author):**

<custom data-type="mention" data-id="id-24">@Kevin Mistry</custom> 

**Duration:** 

\~40 minutes

**Summary:**

New signups going through onboarding where facing error going past the demo booking stage because submit survey was failing.

**Impact:**

New signups within the time frame. Out of the two

**Root Cause:** 

This was a release notes issue. We required ms-accounts to go out along with migration but only migration was included in release notes causing the failure. 

**Action Items:**

Create alerts around submit survey failures, onboarding and investigate the miss in release notes.

‌

**Incident/Alert:**

Rest API developer documents were unavailable, showing a blank white page.

**Prepared by (Author):**

<custom data-type="mention" data-id="id-25">@Michael Griffiths</custom> 

**Duration:** 

\~ 2 hours

**Summary:**

CDN that hosts the file `redoc.standalone.js` removed the file from this location.  This file is used to generate the documents for RestAPI.  Needed to replace the location to the current location.  Site is back up.

**Impact:**

Any customer trying to review the rest api documents would be impacted.  RestAPI itself was fully functional.  We had no reports, this was found internally and corrected and pushed as a hotfix.

**Root Cause:** 

CDN removing/changing the link we were using.

**Action Items:**

A P1 was created <custom data-type="smartlink" data-id="id-26">https://method.atlassian.net/browse/PL-58656</custom> and was hot fixed very quickly after discovery.

‌

**Incident/Alert:** 

Newly created accounts do not see apps on dashboard. Slowness observed and eventually the apps dashboard loads.

**Prepared by (Author):**

<custom data-type="mention" data-id="id-27">@Kevin Mistry</custom> 

**Duration:** 

\~ 2 hours

**Summary:**

A MongoDB migration script (`672_CreateBannerContentAndBannerScheduleCollectionToAllAccounts.cs`) initiated at 9:00 AM EST across all account databases created significant database load on mongo side. This cascaded to the App Update Agent (RabbitMQ consumer) to fail when creating indexes (`AddCmpndIdxVersionIdToScreenInfoAccount` for Runtime.Core.ScreenInfo collection and `AddCmpndIdxFieldTableNameToScreenBaseAccount` for Runtime.Core.ScreenBase collection), resulting in newly created customer accounts seeing blank dashboards with no apps visible after onboarding. The issue was resolved by stopping the migration around 11:00 AM EST, after which apps started appearing instantly for affected customer on apps dashboards.

**Impact:**

* **Customer Impact**: All newly created accounts during the 2-hour window experienced blank dashboards with no apps visible after completing onboarding for a brief time.
* **System Impact**: MongoDB performance degradation due to load, App Update Queue processing backed up, index creation failures requiring retry mechanism and subsequent data dog error logs
* **Customer Experience**: Degraded onboarding experience, potential customer confusion during the incident window

**Root Cause:** 

The MongoDB migration script executed synchronous drop/create operations on two collections (`BannerContentCollection` and `BannerScheduleCollection`) across all accounts. This overwhelmed MongoDB with \~12K operations, triggering WiredTiger's "deferred table drop" mechanism and causing replication lag. The resulting database load caused the App Update Agent to fail during index creation processes, preventing proper app installation for new accounts.

**Action Items:**

* A P0 created and immediate migration stoppage resolved the issue. ([PL-58297](https://method.atlassian.net/browse/PL-58297) )
* Subsequent changes made as suggested by devops to release a hotfix for migration scrip in off hours - [PL-58299](https://method.atlassian.net/browse/PL-58299) 
* index check handling from customer management team for index issue - [PL-58300](https://method.atlassian.net/browse/PL-58300) 


‌

**Incident/Alert:**

Platform-Wide Service Outage / DNS Resolution Failure

**Prepared by (Author):**

<custom data-type="mention" data-id="id-28">@Arash Pakbaz</custom> 

**Duration:** 

\~45 minutes

**Summary:**

The entire platform became inaccessible, with users encountering errors and being unable to log in or access the service. The issue coincided with a morning code deployment and manifested as widespread errors in the Gateway service, specifically `Name or service not known (microservices.method.int:80)`. Initial diagnosis pointed to the deployment, but the true root cause was a **brief failure in DNS resolution** for the private Route 53 zone `method.int`.

**Impact:**

**Critical Customer Impact.** The entire platform was inaccessible to all users, resulting in a **total service outage** for the duration of the incident.

**Root Cause:** 

The Gateway service failed to resolve the internal domain `microservices.method.int`, preventing communication with all downstream microservices.

The DNS failure occurred due to an intermittent, and currently **unknown**, issue within the custom DNS setup:

1. The VPC's DHCP is configured to use our internal DNS server.
2. The internal DNS server uses **conditional forwarders** to direct queries for the private zone `method.int` back to the AWS VPC's default DNS resolver.
3. For a brief period, this forwarding/resolution mechanism failed, preventing the internal DNS server from resolving `method.int` records.

**Action Items:**

1. **Immediate Mitigation:**

    * Temporarily reverted the morning code deployment (this was an initial, though incorrect, mitigation step while the roll-back deployment caused some delays due to another isseu).
    * The service eventually recovered once the intermittent DNS resolution issue cleared.
    
2. **Short-Term/Bypass:**

    * Implemented a specific local fallback mechanism on relevant Linux machines by modifying the `/etc/resolv.conf` file. This new configuration was set to **query the AWS VPC's default DNS resolver directly** for internal domains, rather than relying solely on the internal DNS server to forward the request. This provides a direct, redundant path for resolving `method.int` to prevent future gateway communication failures. (All production machines)
    * [\[PL-57948\] Implement Local DNS Fallback for \`method.int\` for all production machines - JIRA](https://method.atlassian.net/browse/PL-57948)
    
3. **Long-Term Investigation:**

    * **Prioritized DNS Server Migration:** We are currently in the process of replacing our legacy **Windows Server 2012** domain/DNS server to Windows Server 2022. This initiative will be prioritized for immediate completion to upgrade the core infrastructure responsible for DNS resolution and eliminate potential stability issues stemming from the older platform.
    * **Ongoing Investigation:** Continue in-depth investigation into why the conditional forwarding/resolution mechanism failed intermittently today to resolve `method.int` via the VPC's DNS resolver.
    * [\[PL-56710\] Upgrade domain/DNS Windows machines to 2022 - JIRA](https://method.atlassian.net/browse/PL-56710)
    

‌

**Incident/Alert:**

Intermittent General Platform Slowness - Only for Gary Accounts

**Prepared by (Author):**

<custom data-type="mention" data-id="id-29">@Arash Pakbaz</custom> 

**Duration:** 

October 6th, 2025 for approximately 1 hour

**Summary:**

The overall platform experienced **intermittent slowness** for about one hour. Investigation using Datadog metrics and Logstash logs revealed that the **EDA Orchestrator API** was timing out after one minute, which consequently introduced delays in the processing of upstream runtime core requests. 

**Impact:**

The slowness was intermittent and, while noticeable, did not affect all customer accounts. The EDA Orchestrator component is currently only enabled for a select number of "Gary accounts." The intermittent delays in core request processing primarily impacted operations for these specific accounts.

**Root Cause:** 

The EDA Orchestrator API was experiencing connection or processing issues, leading to a consistent 1-minute timeout. The underlying issue was identified as a misconfiguration in the **Load Balancing and/or Deployment Setup** for the EDA Orchestrator API across the production servers (prod-msl-03, 04, and 05).

**Action Items:**

**Resolution:** A ticket was immediately created to address the root cause by fixing the **Load Balancing and Deployment Setup** for the EDA Orchestrator API on the affected production servers.

* _(Related Ticket:_ [_PL-57695_](https://method.atlassian.net/browse/PL-57695) _- Fix Load Balancing and Deployment Setup for EDA Orchestrator API on prod-msl-03, 04, and 05)_

‌

**Incident/Alert:**

Method Classic Platform Slowness

**Prepared by (Author):**

<custom data-type="mention" data-id="id-30">@Arash Pakbaz</custom> 

**Duration:** 

30 minutes

**Summary:**

The Method Classic platform experienced a period of significant slowness for approximately 30 minutes during the day. This incident occurred while the team was attempting to migrate the platform to new servers running **Windows Server 2022**. Traffic was temporarily rerouted back to the old, stable machines to restore performance while investigation continues.

**Impact:**  
Users of the Classic platform experienced noticeable slowness and degraded performance while using the application.

**Root Cause:** 

Under Investigation**.** The slowness is believed to be a combination of issues related to the new Windows Server 2022 environment during the migration process. Initial suspects include:

* Configuration or performance overhead from **Windows Defender Anti-Virus**.
* General performance characteristics or misconfigurations related to the **Windows Server 2022 OS** itself.
* Potential **permission issues** on the new server environment.

**Action Items:**

1. **Immediate Mitigation:** Rerouted traffic from the AWS Load Balancer back to the old, stable servers hosting the Classic platform to immediately resolve the customer-facing slowness.
2. **Investigation & Resolution (Ongoing):** Continue in-depth investigation into the new Windows Server 2022 setup to isolate the exact cause(s) of the performance degradation (e.g., Anti-Virus configuration, OS tuning, permission checks).

‌

**Incident/Alert:** Runtime repeatedly calling ms-account endpoint — caching not working as expected after recent runtime changes.

**Prepared by (Author):** <custom data-type="mention" data-id="id-31">@Hammad Ali Hashmi</custom> 

**Duration:** 4 hours 35 minutes

**Summary:** After recent runtime changes, the caching mechanism failed, causing runtime to repeatedly call the ms-account endpoint instead of serving data from memory cache. This led to increased load and minor customer-facing slowness. A hotfix ([PL-57626](https://method.atlassian.net/browse/PL-57626)) was deployed to restore caching, after which the issue was resolved.

**Impact:** Overall platform-wide slowness and degraded performance were observed during the incident window. Multiple services were indirectly affected due to excessive runtime-to-ms-account traffic, increasing load on backend systems and slowing customer operations such as app publish and update.

**Root Cause:** The issue originated from a change in runtime-core introduced in [PL-57225](https://method.atlassian.net/browse/PL-57225), where updated app publish and app update logic affected caching behavior in the ServiceMap class. The modified line caused runtime to skip memory caching and repeatedly query ms-account.

**Action Items:** Deployed hotfix PL-57626 to restore proper caching and eliminate redundant ms-account calls; verified the fix in Warehouse and production

**Incident/Alert:**

High Memory Usage on RabbitMQ Cluster

**Prepared by (Author):**

<custom data-type="mention" data-id="id-32">@Arash Pakbaz</custom> 

**Duration:** 

29th (Start Date) and ongoing for 4 days (until fix deployment on Oct 3rd)

**Summary:**

The RabbitMQ cluster experienced a prolonged period of **high memory usage** and continuous growth, triggering internal alerts and log errors. The issue was traced to a **memory leak** caused by an excessive and ever-increasing number of persistent connections to the broker. This was specifically found to be due to a misconfigured **health check** mechanism in the **AuditTrail API** service.

**Impact:**  
_Customer Impact:_ None (No service degradation or downtime experienced by external users).

_Internal Impact:_ High (Constant internal alerts, errors logged in Logstash, and the need for manual, periodic restarts of individual RabbitMQ nodes to temporarily release memory, impacting internal team time).

**Root Cause:** 

The AuditTrail API's health check was improperly configured, causing it to establish and hold a **persistent connection** to RabbitMQ on every check. Due to the high frequency of these checks, the number of open connections grew rapidly and continuously (a connection leak), consuming excessive memory on the RabbitMQ nodes. The issue was initially masked because the former Classic Load Balancer did not pass the true client IP, making initial investigation difficult.

**Action Items:**  

1. **Immediate Resolution:**

    * Replaced the old AWS Classic Load Balancer (CLB) with a new AWS Network Load Balancer (NLB) to expose the actual client IPs.
    * Used the exposed IPs to identify the offending services (MSL03 and MSL04 machines).
    * Investigated the connections and identified the source as the AuditTrail API's faulty health check.
    * Fixed the bug in the AuditTrail API health check configuration.
    * Deployed the fix to production.
    * _(Related Ticket:_ [_PL-57675_](https://method.atlassian.net/browse/PL-57675)_)_
    
2. **Long-Term/Preventative Action:**

    * Initiate a project to **migrate the RabbitMQ cluster** to new Ubuntu machines and **upgrade the broker to the latest compatible version** to benefit from newer features, performance improvements, and memory handling capabilities.
    * _(Related Ticket:_ [_PL-57581_](https://method.atlassian.net/browse/PL-57581)_)_
    

‌

**Incident/Alert:**

Datadog detected an increase in 503 errors on gateway ( 58 events)

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-33">@Ismael Sagullo</custom> 

**Duration:** 

approx. 5 minutes

**Summary:**

![](blob:https://media.staging.atl-paas.net/?type=file&localId=0304f0b0-1b1f-4e8f-b2e3-7e61795e4463&id=31fa5791-def9-426d-a06f-c9fbbb8b8066&&collection=contentId-133496969&height=1240&occurrenceKey=null&width=2142&__contextId=null&__displayType=null&__external=false&__fileMimeType=null&__fileName=null&__fileSize=null&__mediaTraceId=null&url=null)
**Impact:**  
There were no mention of the errors in #swat, and there did not seem to be any customer complaints

**Root Cause:** 

The 503 errors were linked to ms-account on prod-msl-04.  
Shortly after ms-account was released, kestrel in ms-account/msl-04 crashed.  
kestrel returned the following error:  
     `Sep 25 12:51:38 ip-172-31-120-89 account[21499]: [12:51:38 ERR] Unexpected Exception`  
     `Sep 25 12:51:38 ip-172-31-120-89 account[21499]: Microsoft.AspNetCore.Server.Kestrel.Core.BadHttpRequestException: Unexpected end of request content.` 

**Action Items:**  
will continue to investigate why kestrel had an issue

‌

**Incident/Alert:**

System-wide performance degradation — Method extremely slow, blank screens, and timeouts.

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-34">@Arash Pakbaz</custom> 

**Duration:** 

approx. 1 hour, with intermittent recovery

**Summary:**

Users and internal team members reported severe slowness across the Method platform, including blank white screens, long load times for runtime screens, and timeouts during login. The issue was observed internally by multiple team members and confirmed by customer reports (e.g., indianaautomotiveequipment at 6:36 AM EST). Investigation showed signs of degraded performance in multiple backend services including RabbitMQ (“rabbit is dead”) and Logstash (very slow to respond). Connectivity to servers was also affected (SSH/RDP timing out). Performance gradually stabilized after \~8:00 AM, with services recovering.

**Impact:**

1. Platform-wide slowdowns, affecting login, dashboard access, and runtime screen loading.
2. Customers unable to use the platform effectively during the incident window.
3. Confirmed customer impact: _indianaautomotiveequipment_ (reported slowness and timeouts at 6:36 AM EST).
4. Internal teams also experienced significant delays accessing Method.

**Root Cause:** 

General Short Answer: Still under investigation. We couldn’t find any anomalies today (or compared to past days between 6AM–8AM) in our dashboards, metrics, etc.1. Datadog Runtime and other major dashboards looked normal.

* We compared major Athena LB logs for timeouts or any response taking more than 10 seconds between today, yesterday, and last week (same time range) — no anomalies.
* We reviewed AWS notifications, zone-to-zone latency, etc. — nothing found.
* We compared major Logstash errors for the same time range — nothing found.
* For "indianaautomotiveequipment", the timeout patterns were not significantly different compared to past days (needs more investigation).
* Users who faced the issue were on different ISPs (Bell, Beanfield, with or without VPN). However, they did not face the issue when using mobile (needs more investigation).
* Although there is no noticeable difference in general timeouts or latency compared to past days, 

**Action Items:**

We will do more investigations:  
a. Compare the number of timeouts and latency for every hour of the day across the past month to identify patterns.  
b. Investigate and determine the major root causes.

 

**Incident/Alert:**

A number of Quickbooks desktop users are reporting while syncing they are receiving an “unrecoverable error” which causes Quickbooks to crash and need to be restarted.  Sync thus is failing to complete

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-35">@Michael Griffiths</custom> 

**Duration:** 

Still ongoing - QuickBooks is investigating as we provide them with support to help them determine what’s going on.

I was able to narrow this down to an issue with QB and how they’re creating references in QB for contacts.  Work around right now is to only create the references in Method, as long as it’s the SDK that creates the references in QB, it seems to work, even updating contacts in QB will work.  Looking at also deploying a new method build for MIE that upon QB crash will let them know the Name of customer/vendor that is causing issue.

**Summary:**

Users are seeing that while the sync is occurring it is failing and causing their QuickBooks application to crash, and need to be started.  Sync thus fails as well.  Looking at the SDK verbose logs, we see that it’s while we are trying to read a specific customer/vendor by their ListID.  Currently we have tickets with QuickBooks and trying to get their help.  It is not just our program that causes it to crash, when running the SDK Tool (QuickBooks tool) with the same request, it also causes QuickBooks to crash.

**Impact:**

It appears to be around 12 customers so far.  More reports keep coming in.

**Root Cause:** 

Ultimately unknown at this time.  We are waiting on QuickBooks to determine the cause.  At this point there is little we can do, cause it’s a read request specifically on a ListID for a customer or vendor. 

**Action Items:**

Awaiting QuickBooks response.  Have been looking at alternate ways to fix, however none of the solutions we found actually fix their files. 

* Verify & Rebuild
* QuickBooks ToolHub

 

‌

‌

**Incident/Alert:**

Users unable to proceed past account selection screen when signing into Classic.

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-36">@Arash Pakbaz</custom> 

**Duration:** 

approx. 36 minutes

**Summary:**

Multiple customers reported being unable to log in to Classic beyond the account selection screen. Initial troubleshooting confirmed the issue affected several accounts (cornerstonetf, cdsanalytical, customequipmentcompanyinc, and others). The issue was reproducible on Chrome but worked in Incognito or other browsers. The problem was traced to token expiry behavior and potential time synchronization between authentication servers. After time synchronization between two machines, affected customers were able to log in successfully without clearing cache or switching browsers.

**Impact:**

1. At least 20+ users on affected accounts were unable to sign in to Classic.
2. Login failures disrupted customer access and workflows until resolution.
3. Workarounds (Incognito/clearing cache) were temporarily provided to impacted clients.

**Root Cause:** 

Time desynchronization between classic and new servers caused token expiry validation failures. This prevented valid tokens from being recognized in normal browser sessions, resulting in login failures.

**Action Items:**  
Classic server is in the process of moving to Windows 2022 and this should solve the issue.

‌

‌

**Incident/Alert:**

[methodintegration.com](http://methodintegration.com) domain redirect to GoDaddy 

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-37">@Arash Pakbaz</custom> 

**Duration:** 

95 minutes

**Summary:**

We received reports of disruptions affecting Method Classic, Report Generation, and the ability to create new Tables & Fields.

**Impact:**

Method Classic, Report Generation, Tables & Fields

**Root Cause:** 

The root cause was an overdue payment for the [methodintegration.com](http://methodintegration.com) domain on GoDaddy.

**Action Items:**  
the domain was bought for three years by Paul and [ops@method.me](mailto:ops@method.me) added to GoDaddy account and credentials was added to Passbolt.

‌

**Incident/Alert:**

Intermittent DNS resolution failures for `microservices.method.int`.

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-38">@Arash Pakbaz</custom> 

**Duration:** 

15 minutes

**Summary:**

Services experienced intermittent connection failures to the internal `microservices.method.int` endpoint, resulting in "Name or service not known" errors. Investigation revealed that internal Windows DNS servers were serving stale, static IP addresses for a dynamic AWS Elastic Load Balancer. The issue was resolved by removing the static records and implementing a conditional forwarder to correctly resolve the hostname via the AWS internal DNS.

**Impact:**

Core API services were unable to communicate with the backend microservices, leading to failed requests and application errors. This caused service degradation and had the potential for user-facing impact.

**Root Cause:** 

The root cause was an incorrect DNS architecture for a hybrid cloud environment. **Static** `A` **records** were configured on internal Windows DNS servers to resolve the hostname of a dynamic AWS Elastic Load Balancer. When the load balancer's underlying IP addresses changed as part of normal AWS operations, the static DNS records became stale and invalid, causing resolution failures.

**Action Items:**  
Remediate DNS configuration for `method.int` by removing static records and implementing a conditional forwarder. See [\[PL-55976\] Intermittent DNS Resolution Failure for microservices.method.int in Production - JIRA](https://method.atlassian.net/browse/PL-55976)

‌

**Incident/Alert:**

Platform slowness for some users

**Prepared by (Author):** 

<custom data-type="mention" data-id="id-39">@Arash Pakbaz</custom> 

**Duration:** 

15 minutes

**Summary:**

Users were experiencing some slowness in general in runtime pages

**Impact:**

Several customers

**Root Cause:** 

It appears the issue was related to one of our RT servers (RT-07) reaching its open file limit. As a result, Nginx stopped processing new requests, causing them to queue up and wait indefinitely.

Datadog metrics suggest that most of the performance degradation stemmed from Redis latency. However, it’s still unclear why this behavior was isolated to RT-07, as no similar anomalies were observed across the other servers.

**Action Items:**  
To prevent similar incidents, we've implemented a new Datadog monitor to track active connection counts and alert us when thresholds are breached. [Monitor Status: Nginx connections are above {{threshold}} | Datadog](https://app.datadoghq.com/monitors/177648203)

‌

**Incident/Alert:**

Some additional fixes were applied to a branch after passed testing and regression on warehouses the updated branch caused blank screens on some apps.

**Prepared by (Author):** 

Alexander Ballard

**Duration:** 

30 minutes

**Summary:**

After deploying the follow up untested build to prod customers and teams started seeing some screens fail to load.  After identifying what had happened everything was rolled back and the previous master put back on prod.

**Impact:**

Several customers were unable to complete their workflows

**Root Cause:** 

Seemed to be down to issues with packages and build configs for method ui.  At some port the legacy packages and build needs to updated.

**Action Items:**  
None at this time. Patches were applied that should prevent merges causing the issue.

‌

---

### **Monday June 16th, 2025**

**Incident/Alert:**  
[PL-55177](https://method.atlassian.net/browse/PL-55177) – Stock App routines are paused in customer accounts

**Prepared by (Author):**  
Hammad Ali Hashmi

**Duration:**  
Routines stopped running around June 10, 2025. The issue was identified and routines were resumed on June 16, 2025.

### **Summary:**

An issue was identified where pausing or resuming a stock app routine in a single customer account unintentionally applied the change across all customer accounts. This caused all stock app routines, such as those for work orders, proposals, and donations to be paused globally. The issue went unnoticed initially and was discovered after noticing a significant drop in routine executions post-June 10.

### **Impact:**

* **Customer Impact:**  
  All customers relying on stock app routines experienced disruption due to routines being paused. Examples include auto-rejections, donation follow-ups, and work order reminders not being triggered.
* **Operational Impact:**  
  Multiple teams, including Customer Management and DevOps, had to investigate and coordinate to identify the root cause and remediate the issue while ensuring affected routines were safely resumed across all accounts.
* **Visibility Gap:**  
  The alerting system did not detect this as the routines were paused (not failed), hence no errors were thrown.

### **Root Cause:**

* The pause/resume functionality for stock app routines was implemented in a way that referenced global routine IDs without filtering by account.
* These routines are stored globally in the MethodAppStore and referenced by individual accounts, but the scheduling documents (JobSchedule) are per-account.
* When a pause or resume action was triggered in any account (even a test or dev account), it affected the schedule entries for all accounts referencing the same global routine.
* The filter used during the pause/resume operation relied solely on the `AppRoutineId` instead of filtering by both `AppRoutineId` and `AccountId`.

### **Action Items:**

* Re-enabled all affected stock app routines via the templatedevv2 interface.
* Added filtering by `AccountId` alongside `AppRoutineId` to isolate changes to a specific account.

---

### **Friday May 23rd, 2025**

**Incident/Alert:**

Customers reported getting invalid ReceivePayment logs ([ticket](https://method.atlassian.net/browse/PL-54549)), it was then discovered that we were creating logs erroneously when cancelling from within shuttle widget.

**Prepared by (Author):**

Greg Hitchon

**Duration:**

**\~**10 days

**Summary:**

We made a change to the stock app execution that did not properly account for cancellations from within the widget. We have no automation and no logs that would catch this sort of thing. This is an accounting field and obviously highly sensitive so it 

**Impact:**

* 38 accounts likely impacted
* 86 total erroneous payment logs created (+ some more that were manually fixed by customers)

**Root Cause:** 

Root cause here is a little tricky, split between:

1. Missing requirements and test cases
2. Team rushing to hit deadlines
3. Lack of knowledge on the team around stock apps and potential issues with certain implementations

‌

**Action Items:**

1. Look into getting a more unified hybrid app dev experience (more training, collaboration, and sharing knowledge)
2. Improving the monitoring and increasing detail of post-sprint checks

---

### **Tuesday May 20, 2025**

**Incident/Alert:**

customers were not able to navigate runtime screens.

**Prepared by (Author):**

[Arash Pakbaz](mailto:a.pakbaz@method.me)

**Duration:**

20 mins

**Summary:**

During the morning deployment of the `runtime-core` API, our Ansible machine failed, causing the deployment to fail. When retried, the process took a long time, and there were code discrepancies between machines (we have four runtime machines).

We believe that when the `runtime-core` services were restarted, a burst of requests overloaded the entire `runtime-core` API, rendering it unresponsive. Additionally, a high number of Redis timeouts was another culprit.

**Impact:**

Outage, customers were not able to access the platform.

**Root Cause:** 

Redis + Ansible.

**Action Items:**

We are discussing the migration of Ansible to its own servers. A new Redis cluster has already been created and passed on to the team for migrating tables and fields. Additionally, one or two heavy Redis users may also be moved to the new cluster.

‌

---

### **Wednesday May 14, 2025**

**Incident/Alert:** Some users noticed slowness or waiting for loading on runtime pages

**Prepared by (Author):** [**Matt Pourasadi**](mailto:m.pourasadi@method.me)

**Duration:** \~30 mins (9:25 AM - 9:55)

**Summary:** We initially received a memory alert on the `prod-rt-04` server due to `AppRoutine.Subscriber.Agent` increasingly consuming memory. As a result, we decided to remove `prod-rt-04` from the `production-runtime-core-api` target group, restart it, and then re-register it back into the group. The default protocol for this target group was set to port 5000. Therefore, when the server was added back, it defaulted to port 5000 instead of 80, which caused requests to `runtime-core-api` on `rt4` to return 404 errors.

**Impact:** all users, it was intermittent depending on the requests hitting one of our four runtime servers 

**Root Cause:** Although the `AppRoutine` issue requires its own investigation, the primary cause of the runtime blank screen and slowness was that `rt4` (`runtime-core-api`) was listening on the wrong port.  
**Action Items:**. Two actions item for the fix: 

1. Fixing the approutine that caused the issue to prevent further memory issues.   
  <custom data-type="smartlink" data-id="id-40">https://method.atlassian.net/browse/PL-54148</custom>  
2. Creating and moving runtime-core-api to new target group with proper default port,   
  <custom data-type="smartlink" data-id="id-41">https://method.atlassian.net/browse/PL-54150</custom>  

### **Wednesday May 13, 2025**

‌

**Incident/Alert:**

Elasticsearch began struggling to process messages, causing them to accumulate in RabbitMQ. Our policy states that queues can hold only up to 40,000 messages; if they exceed this limit, they end up in the `error` queue.

**Prepared by (Author):**

[Arash Pakbaz](mailto:a.pakbaz@method.me)

**Duration:**

5 hrs.

**Summary:**

‌

**Impact:**

Intermittent issues occurred between 10 and 11 PM, with some customers encountering random error messages. However, throughout the day, there were no errors—only general slowness.

**Root Cause:** 

Elasticsearch reached its high disk space watermark and started to put indices in read-only mode and not accepting any new request. 

‌

**Action Items:**

Increased the size of data drives and upcoming cluster migration to v9.0 will solve the issue.

‌

### **Monday Apr 23rd, 2025**

**Incident/Alert:** Some users were unable to sign in for a few minutes

 [PL-53896: SignIn: Some users get 400 errors during a hotfix release](https://method.atlassian.net/browse/PL-53896)

**Prepared by (Author):** [**San Oo**](mailto:s.oo@method.me)

**Duration:** \~2mins (3:35 pm - 3:37 pm)

**Summary:** Admin team released a hotfix for the sign-in issue, and some users were unable to sign-in during that time, but were able to successfully log in shortly afterward.

**Impact:** 29 users

**Root Cause:** The error suggested that HMAC validations failed for those users during that period of time.

**Action Items:** To implement a fail-safe mechanism in the sign-in process to prevent such failures during releases.

### **Monday Apr 14th, 2025**

**Incident/Alert:**

Classic users experienced issues with page loading or getting stuck during sign-in.

‌

**Prepared by (Author):**

 [**Matt Pourasadi**](mailto:m.pourasadi@method.me)

**Duration:**

\~1hr  (1:14 PM – 2:02 PM) = 5 mins of the main issue, later with workaround for browser cache

**Summary:**

During this period, DevOps (Matt) was replacing the load balancers/routing for Classic servers from Classic Load Balancers (CLB) to Application Load Balancers (ALB). This change unintentionally caused sign-in issues for Classic users.

Although QA (Yuri) was actively testing the change as it was deployed, the issue wasn’t immediately detected because it only manifested during fresh sign-ins. Existing sessions or cached credentials didn’t expose the problem.

The issue was noticed shortly afterward in the `#swat` channel. The changes were rolled back within a minute. However, due to browser caching, affected users continued to experience the issue for several more minutes.

‌

**Impact:**

Based on the logs, seven Classic accounts encountered sign-in issues due to page loading failures. Support advised affected users to clear their browser cache or use incognito mode, which resolved the problem.

‌

**Root Cause:**

The Classic application includes IIS redirect rules that route to external servers via SSL. The new ALB setup did not initially account for these rules, leading to the failure.

‌

**Action Items:**

* An SSL certificate was added to the new ALB later that evening.
* A separate target group was created for HTTPS traffic to properly handle secure redirects.
* From a QA perspective, lessons learned include:  
  Avoid making such changes during working hours.

Ensure testing includes both pre-authenticated sessions and fresh sign-ins, using different browsers to identify cache-related issues.

### **Thursday Feb 27th, 2025**

**Incident/Alert:**

High XSS Analytics events causing outage [PL-52451: MethodUI not loading](https://method.atlassian.net/browse/PL-52451)

**Prepared by (Author):**

[**Benjamin Grady**](mailto:b.grady@method.me)

**Duration:**

\~1hr  (8:36 AM – 9:42 AM)

**Summary:**

A recent change to our sanitization discrepancy tracking logic caused an unexpectedly high volume of requests to our analytics service, overwhelming its capacity and resulting in an outage. The change was intended to improve our ability to track discrepancies between user-provided data and sanitized data, but due to issues in the implementation, it generated excessive and redundant API calls.

**Impact:**

Users experienced an outage

**Root Cause:** 

1. _**Development**_

_Lack of Initial Volume Estimates:_

* The change introduced new logic to track sanitization discrepancies, but since the quality of incoming data was unknown, we had no prior estimate of how frequently calls to the analytics service would be made.

_No Batching or Deduplication Mechanism:_

* Every detected discrepancy triggered an API request, leading to redundant calls even when multiple discrepancies were similar or repeated.

_Faulty Comparison Logic:_

* The logic comparing raw and sanitized data incorrectly flagged minor variations (such as attribute order, spacing, and extra closing tags) as discrepancies, significantly inflating the number of requests.
* In one case, we were comparing to objects instead of primitives, which caused a large volume increase

2. _**Infrastructure**_

_MethodPheonix as a Proxy_

* Since the outage was in MethodPheonix, and no changes were made there, with errors appearing in other services, it is easy to confuse the source of the outage

_Sql Errors_

* Logstash showed huge amounts of error regarding SQL Server reaching to max of connection pool. We had around 4000 open connections in sql-prod1 that brought our whole system down (we usually have around 1500 per server during pick time)
* ms-analytics should be independent from sql server but usually there are some enrichment/fetching data for it

3. _**Rollback Process**_

* The release manager asked DevOps to investigate first due to uncertainty about if the issue was 

    * Release-related
    * Server related
    * Code related
    
* The confusion in part was due to recent changes in architecture – we recently added 2 new servers. Investigation about the server configuration delayed the rollback.

**Action Items:**

1. Roll back runtime-core and method-ui
2. Create follow-up ticket with improved analytics logic

    1. Improved comparison logic
    2. Client-side de-duplication
    3. Feature-flagged
    
3. Examine network request volume as part of QA process through puppeteer [PL-52454: Monitor network requests for page load in Playwright](https://method.atlassian.net/browse/PL-52454)
4. Investigate decoupling ms-analytics from SQL
5. Consider refactoring out analytics calls from MethodPheonix
6. Discuss process improvements to ensure faster rollback decisions going forward

### **Wednesday Feb 26th, 2025**

**Incident/Alert:**

A bug with the mornings releases saw that deleting in method US accounts was not being sent to QB/Xero

**Prepared by (Author):**

[Michael Griffiths](mailto:m.griffiths@method.me)

**Duration:**

8 days

**Summary:**

Found a missing bracket in logic, that wasn’t throwing an error, and wasn’t sending it to be synced (didn’t set servertimemodified).

**Impact:**

Around 500 accounts

**Root Cause:** 

**Root Cause Analysis and Remediation:**

Code change needed to be fixed.  Essentially just adding the bracket to properly go through the code.

**Action Items:**

Pushed a hotfixed.  Got a list of affected customers, going to have support reach out.

Hotfix was deployed, reaching out to customers is in progress.

### **Wednesday February 12th, 2025**

**Incident/Alert:**

Ticket [here](https://method.atlassian.net/browse/PL-52097). BonOpusSales was compromised and sent out some crypto scam emails.

**Prepared by (Author):**

Greg Hitchon

**Duration:**

\~2hrs

**Summary:**

Had an issue with a compromised account sending out some crypto scam emails. In total 935/32000+ emails went out. The rest were blocked by our automated system and removed from the queue. 

Automated alert triggered at 9:54 PM Feb 11th  blocking all emails

Logins were disabled by \~11:30 PM Feb 11th

Notifications were removed from account 10:00 AM Feb 12th

Account was unblocked and admin gained back access \~10:30 AM Feb 12th

‌

**Impact:**

935 scam emails were sent out

**Root Cause:** 

Account login was compromised. Rate limit worked but more advanced login controls and pro-active spam blocking has not yet been implemented. Similar root cause to [PL-49712: Yahoo blocking IP 149.72.194.74 and 149.72.45.198](https://method.atlassian.net/browse/PL-49712)

**Action Items:**

‌

| **Status** | **Task** | **Assigned To** |
| --- | --- | --- |
| **Done ✅** | Re-enable the identities to for the account and wipe the passwords and expire the v1 tokens. The users will need to use forgot password to create new passwords to login, please ensure they don't choose the last compromised ones.   | [Richard Pangborn](mailto:r.pangborn@method.me) [Inder Dhaliwal](mailto:i.dhaliwal@method.me) |
| **Done ✅** | investigating audit trail to determine if anything else was done maliciously  | [San Oo](mailto:s.oo@method.me) |
| **Done ✅** | clean up notification history | [Gregory Hitchon](mailto:g.hitchon@method.me) |
| **Pending** | investigating logs to determine access was granted. | [Matt Pourasadi](mailto:m.pourasadi@method.me) |
| **Done ✅** | work with marketing/support to contact accounts that were sent malicious emails.  | [Hannah Johnston](mailto:h.johnston@method.me) |
| **Pending** | Work with devops/greg to fill out postmortem with additional followups. Some items added below: Can we review previous incident logs as this is a repeat offense and determine if mitigation steps were followed correctly?  San: There was only one failed sign-in attempt made by the spammer last night, and they successfully logged in on the second attempt. It doesn't seem like a sophisticated brute-force attack. It's likely that the Admin is using the same password on other sites, and the spammer obtained the password somehow and gave it a shot.  What new mitigation steps come out of this one?  San:  We have advised the customer to enable 2FA.  Admin team will setup a monitoring task to check the SignInActivity data to identify suspicious logins based on risk scores and post an alert to our Slack channel. It's going to be a manual review until we implement SignIn Fortification phase 2, which will introduce more robust features like sending passcode verification emails. How can we run a playbook that does not directly involve senior leaders eg Are our managers/leads empowered enough to execute here?  | [Hannah Johnston](mailto:h.johnston@method.me) [San Oo](mailto:s.oo@method.me) |
|  |  |  |

‌

### **Thursday Jan 15th, 2025**

**Incident/Alert:**

A bug with the mornings releases meant some screens with drilldown grids on charts. Weren’t loading.

**Prepared by (Author):**

[Alexander Ballard](mailto:a.ballard@method.me)

**Duration:**

30 min

**Summary:**

We found an issue affecting a small numbers of screen  in the logs after the release and rolled back.

‌

**Impact:**

A handful customers

**Root Cause:** 

**Root Cause Analysis and Remediation:**

Code change needed to be fixed.

‌

**Action Items:**

Code change needed to be fixed.

‌

### **Thursday Jan 2nd, 2025**

**Incident/Alert:**

Service disruption loading screens 

**Prepared by (Author):**

Arash

**Duration:**

1 hr

**Summary:**

We experienced some service disruptions on January 2nd that impacted customer access to Method. After thorough investigation, we've identified the following contributing factors:

StockApp Release Surge: Multiple StockApp releases on that day led to a surge in requests on the Tables & Fields microservice, resulting in high CPU usage.

ms-search API Bottleneck: The ms-search API was also consuming excessive CPU resources intermittently.

Resource Contention: These two services competed for CPU resources on both MSN01 and MSN02, ultimately leading to a server crash and restart.

‌

**Impact:**

Most customers

**Root Cause:** 

**Root Cause Analysis and Remediation:**

Tables & Fields: We've been aware of the resource-intensive nature of the Tables & Fields microservice and have had ongoing discussions about optimization.

ms-search: Further investigation revealed code smells and inefficient handling of recently visited Contact records in the ms-search API. Refactored the ms-search project, addressing the performance bottlenecks and upgrading it to .NET 8.0.

‌

**Action Items:**

Refactored the ms-search project, addressing the performance bottlenecks and upgrading it to .NET 8.0.

We temporarily upsized both MSN servers to increase available resources.

We reverted recent ms-search changes as a precautionary measure.

‌

‌

### **Tuesday December 10th, 2024**

**Incident/Alert:**

Shuttle deployed a bad release on their side

‌

**Prepared by (Author):**

Elliot Ruiz 

‌

**Duration: \~70 mins**

‌

**Summary:**

Roughly 10 customers reported that they couldn’t make payments due to a bug on shuttle's side that prevented them from using their saved credit cards on the widget.

‌

**Impact:**

10 customers reported they couldn’t use any of their saved credit cards due to the issue

‌

**Root Cause:**

Shuttle stated that:   
_We’ve tracked it down to this parameter you pass in to restrict checkout to CARDS and ACH_  "payment_method_type":\["CARDS","ACH"\] _in particular it seems, when the client doesn’t actually have ACH enabled._

While we didn’t necessarily intend to support this historically, it makes sense, so we’ll fix it

‌

**Action items:**

Reported the issue to shuttle, and they hot fixed the issue

### **Friday December 6th, 2024**

**Incident/Alert:**

New Malicious validation rules were preventing customers from complete some workflows 

‌

**Prepared by (Author):**

[Alexander Ballard](mailto:a.ballard@method.me)

‌

**Duration: 60 mins**

‌

**Summary:**

New Malicious validation rules were rolled out to prevent injection attacks.  Some existing customer  data was now being blocked by the new rules.

‌

**Impact:**

3 customers reported they couldn’t complete work flows

‌

**Root Cause:**

Intended functionality, investigation ticket created to see if we can provide work a round for the customers with issues.  Still need product decisions on how we want to go forward. 

‌

**Action items:**

Switched off feature flag.

‌

### **Friday December 4th, 2024**

**Incident/Alert:**

An edge case where customers were using an editable grid and changed a value from null to a value after saving the record caused the new value to be ignored. 

‌

**Prepared by (Author):**

[Alexander Ballard](mailto:a.ballard@method.me)

‌

**Duration: 60 mins**

‌

**Summary:**

Changes to grid meant that duplicate data was being returned when numbers were blank causing an issue where changes to numbers were happening.

‌

**Impact:**

4 customers reported they couldn’t complete work flows

‌

**Root Cause:**

This specific workflow was changed and the effect not covered in any existing tests so wasn’t noticed until discovered by customers

‌

**Action items:**

Release reverted.

‌

‌

‌

### **Friday November 22nd, 2024**

**Incident/Alert:**

Customers were able to access other accounts they didn’t have access to ([ticket](https://method.atlassian.net/browse/PL-50247))

‌

**Prepared by (Author):**

[Sharad Shivmath](mailto:s.shivmath@method.me)

‌

**Duration: \~50 mins**

‌

**Summary:**

This issue was first discovered due to trying to access a dashboard in Alocet while logged in as Method Support. The dashboard also loads unexpectedly.

Also then tried logging in to different accounts and you get way further than you should, able to go to account pages (no data) and get a bunch of errors.

There are also some cases where it displays a “GetAccess” screen before turning white with a bunch of users listed to contact.

‌

**Impact:**

Users were able to access other accounts they didn’t have access to 

‌

**Root Cause:**

To fix the issue in the ticket[ PL-46800](https://method.atlassian.net/browse/PL-46800), before signing out, we were checking if the token is active or not in SignIn and method-platform-ui. 

‌

**Action items:**

Revert [ticket ](https://method.atlassian.net/browse/PL-50247)

### **Thursday November 14th, 2024**

**Incident/Alert:** 

Customers were unable to use the method app on iPad  ([ticket](https://method.atlassian.net/browse/PL-50066))

‌

**Prepared by (Author):**

Elliot Ruiz

**Duration: \~1hr**

**Summary:**

We received reports from customers who were unable to use the Method app on iPad because the content view shrank, making it almost unusable.

‌

**Impact:**

Every user using the method app on an iPad. We received  +3 reports of this issue

‌

**Root Cause:** 

To fix the issue on this [ticket](https://method.atlassian.net/browse/PL-50066), we removed unnecessary overflow settings that were causing two unwanted scrollbars to render in iframes. Because our Method app is mounted within an app view, the platform interpreted it as an iframe and removed essential CSS properties, preventing the content from displaying at full size.

‌

**Action Items:**

1. Revert root cause [ticket](https://method.atlassian.net/browse/PL-50066)
2. Close up root cause [ticket ](https://method.atlassian.net/browse/PL-50066)as will not fix

‌

### **Wednesday November 6th, 2024**

**Incident/Alert:** 

Sub-user 4 was suspended by SendGrid ([ticket](https://method.atlassian.net/browse/PL-49883))

**Prepared by (Author):**

[**Gregory Hitchon**](mailto:g.hitchon@method.me)

**Duration: \~1hr**

**Summary:**

SendGrid suspended one of our sub-users (fallback + marketing). Mail in progress there was unable to be sent, and was never recovered.

‌

We switched over the mail stream to sub-user 2, which previously had a bunch of spam in it, but had since expired. This was done via hot fix.

‌

We reached out immediately to SendGrid support, but was a slow process and the account was only reinstated days later.

**Impact:**

On the order of hundreds of marketing mail was not sent out.

**Root Cause:** 

SendGrid automatically flagged our account. They said it was due to some suspicious testing (sending out a test email campaign) and we could stop this from happening by using a approved IP list and rotating our keys.

**Action Items:**

3. Rotate our keys [ticket](https://method.atlassian.net/browse/PL-49961)
4. Add all known IP’s to the allow list (if possible) [ticket](https://method.atlassian.net/browse/PL-49963)

### **Friday Oct 31, 2024**

**Incident/Alert:**

Customers who are connected to <custom data-type="smartlink" data-id="id-42">http://Authorize.Net</custom>  via Shuttle were not able to successfully process payments. [Ticket](https://method.atlassian.net/browse/PL-49765)

**Prepared by (Author):**

Sammy Yusuf

**Duration:**

\~48 hours

**Summary:**

A P0 was raised at approximately \~10AM on Oct 29, 204. Some customers who were attempting to make a payment in the widget started to notice they were seeing a red error message related to a failure of refresh access tokens.

We reached out to the shuttle team to get some more information related to this issue, and it was determined the <custom data-type="smartlink" data-id="id-43">http://Authorize.Net</custom>  payment gateway was not refreshing the access tokens. <custom data-type="smartlink" data-id="id-44">http://Authorize.Net</custom>  was undergoing some maintenance for approximately the last \~7 days and on the day of the issue, their wa an interruption to their API service related OAuth.

‌

The access tokens used are valid for approximately \~24 hours so as access tokens continued to expire, the effect became more widespread because of the failure to refresh the access tokens. 

Within the same day, <custom data-type="smartlink" data-id="id-45">http://Authorize.Net</custom>  did post to their incident [page ](https://status.authorize.net/history)of the ongoing issue and was marked as resolved around the evening. However, the issue continued to progress into the next day again which prompted <custom data-type="smartlink" data-id="id-46">http://Authorize.Net</custom>  to post another report to their incident page of the ongoing issue.  The issue was finally resolved by <custom data-type="smartlink" data-id="id-47">http://Authorize.Net</custom>  and Shuttle confirmed the affected accounts are now in a good state. 

**Impact:**  
The impact was limited in it’s scope to <custom data-type="smartlink" data-id="id-48">http://Authorize.Net</custom>  customers who were connected to shuttle via OAuth. 

**Root Cause:** 

3rd party maintenance by <custom data-type="smartlink" data-id="id-49">http://Authorize.Net</custom>  interrupting their API Service for OAuth. 

**Action Items:**  
Look into if any clearer communication is required during this time. We recently added some some segment properties identifying customers with active shuttle gateways allowing us to target connected accounts with app cues

### **Friday Oct 25, 2024**

**Incident/Alert:**

Yahoo began blocking IP’s due to a compromised account (soldiersports) sending out 90k+ spam emails [PL-49712: Yahoo blocking IP 149.72.194.74 and 149.72.45.198](https://method.atlassian.net/browse/PL-49712)

**Prepared by (Author):**

Greg Hitchon

**Duration:**

\~18 hours

**Summary:**

A P0 was raised at \~9 AM after alerts were noted in the Impact alerting channel regarding IP address blocks by Yahoo. We first looked to restore sending however noticed that the emails in question were spam emails (crypto nonsense) form soldiersports. It would later be determined that this account was compromised.

‌

We had a number of pending spam emails on our Marketing fallback subuser and so the plan was made to create another subuser and sacrifice all current mail on the existing subuser (subuser 2).

‌

We transitioned our Marketing fallback mail to the new subuser 3 however it was soon noted that mail was still sending. We had thought the process of suspending an account cancels all running app routines however this is not the case.

‌

We quickly removed IP’s from that account and created another subuser (subuser 4). We added a manual block in the code for the soldiersports account and made the transition. This is the current state we are in today.

‌

The fallout of this issue was that 3 out of the 4 customer IP’s were blocked by Yahoo. For a few hours we were not sending mail from Yahoo in our Marketing fallback stream. However, Yahoo unblocked the IP in that stream and we were back to full functionality by 3 AM on the 26th (actual time was sooner, but this is when it was confirmed).

‌

In order to limit the damage if the spammers had other accounts we implemented a hard rate limit of 100 marketing, 500 transactional for the weekend. We monitored this but had no issues.

‌

Note: to complicate matters SendGrid also had an outage during this time. This lasted about 30 minutes, during which time no mail was sent out.

‌

**Impact:**

Our deliverability could take a huge hit. Had to notify customers of outage. All customers were unable to send mail from Marketing fallback stream to Yahoo domains for hours (hard to pin down specifics as Yahoo may have blocked/unblocked in this time)

**Root Cause:** 

Ineffective spam prevention

**Action Items:**

1. There are a broad range of action items, but currently we are taking a summary of recommendations to leadership to decide the best course of action

### **Friday Oct 18, 2024**

**Incident/Alert:**

Background Sync/Webhooks failing for some account \~ 75 then dropped to around 10/20. 

**Prepared by (Author):**

Michael Griffiths

**Duration:**

Oct. 18, 2024, \~ 4PM - Oct 25, 2024 \~ 2AM (About 2 hours for the 75, then still ongoing for the 10ish, which is now around 20 till end date)

**Summary:**

_Quickbook got back to us, and acknowledged that the issue is on their end and are currently investigating/working on it. Today 2024-11-07 QB confirmed they fixed it on their end._

‌

Quickbooks CDC responses in xml aren’t being properly encoded (Specifically for & and “ symbols).  This isn’t for every CDC (Change Data Capture) response, it only appears to affect a small percentage of our accounts.

‌

**Impact:**

\~20ish accounts are affected currently, mostly with the “ symbol not being encoded.

**Root Cause:**

QB is not properly encoding their XML on CDC requests (Change Data Capture)

**Action Items:**

We have a case ticket logged with QB to hopefully get them to resolve the issue.  We have a potential hotfix that we will apply if QB doesn’t.

‌

Quickbooks fixed it.  Started properly encoding their CDC endpoints.

### **Tuesday Oct 8, 2024**

**Incident/Alert:**

Shuttle went down entirely. 

**Prepared by (Author):**

Greg Hitchon

**Duration:**

\~4 AM - \~4 PM ET. (24 hrs)

**Summary:**

From shuttle: 

**On Oct 8, 2024 Shuttle went offline at 9:11am BST and was unavailable until 20:45 BST. This was due to the**

**database loss of a critical system and a failure of its redundancy measures.**

**This incident did not result in the loss of any data and is not a security related incident**

**Impact:**

All payments were down, briefly we also lost the ability to go to the portal at all (resolved by an impact HF)

**Root Cause:**

Shuttle had some massive issues with a database and the restore process.

**Action Items:**

Potentially move away from shuttle, investigate how we handle general third party dependencies.

### **Monday Oct 7, 2024**

**Incident/Alert:**

Criteria Editor was broken in some cases after change with that morning's release. Fixes related to the previous outage caused new issues.

**Prepared by (Author):**

[Alexander Ballard](mailto:a.ballard@method.me)

**Duration:**

9 AM - 2 PM ET. (6 hrs)

**Summary:**

Changes made to the action editor to flag between two versions broke some parts of criteria builder.  Fixes related to the previous outage caused new issues.

**Root Cause:**

Overly complex and spaghetti code led to these unexpected changes.

**Action Items:**

Additional cases added as part of future testing.

### **Tuesday Oct 3, 2024**

**Incident/Alert:**

Criteria Editor was broken in some cases after change with that mornings release. 

**Prepared by (Author):**

[Alexander Ballard](mailto:a.ballard@method.me)

**Duration:**

9 AM - 2 PM ET. (6 hrs)

**Summary:**

Changes made to the action editor to flag between two versions broke some parts of criteria builder.

**Root Cause:**

Overly complex and spaghetti code led to these unexpected changes.

**Action Items:**

Additional cases added as part of future testing. 

### **Wednesday Sept 18, 2024**

**Incident/Alert:**

‌

**Prepared by (Author):**

[Michael Griffiths](mailto:m.griffiths@method.me)

**Duration:**

24hr

**Summary:**

The Gmail sidebar had some issues with using it.  Essentially the page needed to be refreshed and the user needed to sign in again, as we are using a different authentication.

**Impact:**

All sidebar users that were connected to the sidebar the previous day and didn’t re-login the new day (eg. left it open overnight).

**Root Cause:** 

New authentication wasn’t compatible with the old authentication.

**Action Items:**

1. New test cases for SSO/authentication with sidebar.

‌

### **Wednesday Sept 13, 2024**

**Incident/Alert:**

‌

**Prepared by (Author):**

[Alexander Ballard](mailto:a.ballard@method.me)

**Duration:**

1hr

**Summary:**

New sign ups were erroring on the first on boarding page.  Leaving in signup  in a broken state.

**Impact:**

It was quickly discovered and we reached out to the customer who failed to signup after ms-preferences-api was rolled back.

**Root Cause:** 

The issue comes from the fact that signup passes a list of feature flags to ms-preferences of account creation but if that call fails ms-preferences has no mechanism to initialize the preferences collection. The reason it failed was down to preferences not handling deleted or renamed feature flags correctly.

**Action Items:**

2. Update preferences initialization end point to ignore unknown feature flags and instead of failing.

### **Tuesday Aug 23, 2024**

**Incident/Alert:**

‌

**Prepared by (Author):**

[Benjamin Grady](mailto:b.grady@method.me)

**Duration:**

1hr

**Summary:**

While examining some bounced/deferred email patterns from throughout the week, we made some changes to the IP sending configuration, disabling all emails that are sent without a specified subuser. This was caught within 3 hours, and took another hour for the delayed emails to finish sending.

**Impact:**

Emails not sent include signup emails, action reminders and possibly others. No complaints were received by clients, but this could have an impact on onboarded accounts

**Root Cause:** 

Lack of understanding of the configuration options in the sendgrid dashboard. While all subusers are explicitly listed, the parent account is also used to send emails, and is configured with a checkbox.

**Action Items:**

3. Meet with the team to show how the configurations are made
4. Improve the [Runbook](https://docs.google.com/document/d/1YoiemFgPMqWZNKNzTTDToH_9iuxk6-iqZHpMa5uDpbA/edit#heading=h.74b3m64ueqpp) to include more details on how subusers relate to IPs and IP pools, and how each subuser is used throughout the codebase.

### **Wednesday Aug 28, 2024**

**Incident/Alert:**

`(Ticket)`

**Prepared by (Author):**

[Gozde Bulut](mailto:g.bulut@method.me)

**Duration:** 

\~43 days (July 16 to Aug 28) 

**Summary:**

We’ve got this p0 where customers with canceled accounts were receiving payment emails from Method. 

**Impact:**

Only a handful of customers with canceled accounts received this payment email. However, it appears that around 125 inactive accounts and 1,265 active accounts may be affected by the Intercom synchronization issue.

**Root Cause:** 

Upon further investigation, it turned out these emails were actually sent by Intercom, and our Intercom sync was disrupted for several accounts because the FeatureFlagList company field was longer than max allowed size (255 characters).

**Action Items:**

The fix, which has been released as hotfix, addresses the issue for active & inactive accounts that are updated during nightly sync. The team also has backfilled data for possible 125 inactive accounts to prevent email triggering. 

The team will continue monitoring the issue, also will be looking at [implementing more observability for Intercom sync.](https://method.atlassian.net/browse/PL-48592)

‌

‌

‌

### **Friday August 8, 2024**

**Incident/Alert:** [**Horizontal Grid Scroll - Unable to scroll through the columns on the grid**](https://method.atlassian.net/browse/AS-11986)

**Prepared by (Author):** [**Alexander Ballard**](mailto:a.ballard@method.me)

**Duration:** \~2hrs

**Summary:** A bug to grid widths resulted in disabling the horizontal scrolling functionality.  This was missed in testing but noticed on a handful of customized screens that use this functionality.

**Impact:** Users of some screens on some devices couldn’t scroll their editable grids

**Root Cause:**  A change to improve sizing didn’t ensure horizontal scrolling still worked.

### **Action Items:** Need to ensure that both features can work in concert and testing covers both.

### **Friday August 2, 2024**

**Incident/Alert:**

[**Send Email - Unable to open attached PDF when the transaction is emailed**](https://method.atlassian.net/browse/PL-48127) 

**Prepared by (Author):**

[**Gregory Hitchon**](mailto:g.hitchon@method.me) **☠️**

**Duration:**

\~2hrs

**Summary:**

We punished changes with a bad defect that got through testing. From around 9 AM to 11 AM attachments above 8kb were being compressed incorrectly and so were corrupted. 

**Impact:**

Users receiving these emails would be unable to open them. This impacted all accounts.

**Root Cause:** 

When encoding base64 in chunks you need to have a chunk size divisible by 3. We did not so it caused corruption. When testing we were using text/csv files which when opened looked fine (first 8kb were good). 

This was a miss in terms of test cases both local dev and QA.

**Action Items:**

1. Need to consider more automation in this area
2. More complete analysis of potential impact when deploying

### **Monday July 29, 2024**

**Incident/Alert:**

`(Ticket)`

**Prepared by (Author):**

[Gozde Bulut](mailto:g.bulut@method.me)

**Duration:** 

\~1 hour (July 29 15:17 PM to July 29 16:26 PM) 

**Summary:**

Account knollinvestments was unable to login to Method

**Impact:**

Only 1 account: knollinvestments

**Root Cause:** 

The account data seems to have gone missing in the MongoDb - Account collection.

‌

**Action Items:**

The issue has been resolved in the P0 ticket by inserting account data into Account collection and [a new ticket](https://method.atlassian.net/browse/PL-48047) has been created to investigate the root cause of the issue.

‌

‌

### **Friday July 26, 2024**

**Incident/Alert:**

Issue with emails not delivering to Yahoo! and AOL customers. [Ticket](https://method.atlassian.net/browse/PL-47999)

**Prepared by (Author):**

Hannah 🔥

**Duration:**

\~30 minutes 12:00 PM  - 12:30 PM 

**Summary:**

Another of our IP addresses got flagged for the same issue we saw on Thursday July 25. 

Email deliverability to <custom data-type="smartlink" data-id="id-50">http://yahoo.com</custom> , <custom data-type="smartlink" data-id="id-51">http://aol.com</custom>  and related domains was impacted. Not all mail was impacted due to multiple IP's in use but a significant percentage. 

**Impact:**

There was essentially no impact here, the IP was unblocked quite quickly and emails processed as expected.

**Root Cause:** 

Email traffic diverted when IP 167.89.91.86 was blocked yesterday caused the problem to propagate to IP 149.72.215.137  

**Action Items:**

* See Thursday July 25 incident

### **Thursday July 25, 2024**

**Incident/Alert:**

Issue with emails not delivering to Yahoo! and AOL customers. 

[PL-47997: Yahoo temporarily blocking emails from](https://method.atlassian.net/browse/PL-47997)

**Prepared by (Author):**

Hannah 👏

**Duration:**

\~14 hours 4:00 AM  - 7:00 PM 

**Summary:**

Email deliverability to <custom data-type="smartlink" data-id="id-52">http://yahoo.com</custom> , <custom data-type="smartlink" data-id="id-53">http://aol.com</custom>  and related domains was impacted. Not all mail was impacted due to multiple IP's in use but a significant percentage. We disabled IP 167.89.91.86 and backlogged emails sent as expected. 

**Impact:**

\~100 accounts affected

**Root Cause:** 

Yahoo has some automated systems for blocking IPs that send too much mail, or too much bad quality mail to their systems. It is impossible to know which occurred, however a safe assumption based on timing is that it was due to user complaints.

**Action Items:**

* Adding further monitoring for IP 167.89.91.86 to identify similar issues faster
* Investigating bulk email limiting and queue fairness policy to prevent future incidents
* Identify accounts with high email volume and problematic sending practices and start customer outreach 

### **Wednesday July 24, 2024**

**Incident/Alert:**

Issue with stock Printable Estimate print template for QBDT accounts, where the item purchase cost was appearing under “Rate” instead of the sales price.

<custom data-type="smartlink" data-id="id-54">https://method.atlassian.net/browse/PL-47942</custom>  

**Prepared by (Author):**

Phil

**Duration:**

 134 days

**Summary:**

The Printable Estimate print template’s Rate column for line items was mapped to the EstimateLine.Rate field, which for QBDT accounts will commonly hold the item’s purchase cost, and not the sales price. 

**Impact:**

All QBDT signups between March 12 2024 and July 24 2024 (151 active accounts)

**Root Cause:** 

This issue was introduced \~4.5 months ago as a fix to a previous, different issue (<custom data-type="smartlink" data-id="id-55">https://method.atlassian.net/browse/PL-45710</custom> ) 

As per the previous ticket above, this print template was showing the total amount under the Rate column. The fix that was implemented was to remap the column to display the EstimateLine.Rate field instead.

For QBDT accounts though, when using markup calculations on estimates, this field holds the item’s purchase cost.

The column was remapped to the calculated field calcRate instead, which displays the expected value.

**Action Items:**

Continue to have more oversight, discussions, and grooming as a team on all new bug tickets that come in, to confirm the solution approach.

This was partly caused by a general lack of knowledge from the team on some of the more technical/accounting-related intricacies of the platform; Phil to work with the team on identifying potential other areas and details that are currently not known or understood.

### **Wednesday July 10, 2024**

**Incident/Alert:**

Issue with Poiesis performance improvements/general grid issue that was made worse

[PL-47668: Unable to create an estimate, invoice from work order](https://method.atlassian.net/browse/AS-11910)

**Prepared by (Author):**

Michael/Alex

**Duration:**

 2 hours \~8:50am - 10:39 

**Summary:**

‌

‌

**Impact:**

TBD

**Root Cause:** 

TBD

**Action Items:**

TBD

‌

‌

### **Wednesday July 04, 2024**

**Incident/Alert:**

RT05 and RT06 machines crashed on July 4th.

**Prepared by (Author):**

Arash

**Duration:**

\~30 min, at around 4:30 AM

**Summary:**

Enabling datadog agent for app routine subscribers caused memory and CPU spikes and eventually crashed both machines. 

**Impact:**

None. no customer facing issue, just less number of nodes for RT apis

**Root Cause:** 

Datadog agent and enabling profiling for app routine subscriber.

**Action Items:**

For now tracing is disabled for the agent, but will investigate and possibly lower the sampling rate to see if it helps.

‌

### **Wednesday July 03, 2024**

**Incident/Alert:**

`(Ticket)`

**Prepared by (Author):**

[Gozde Bulut](mailto:g.bulut@method.me)

**Duration:** 

\~27 hours (July 02 9:00 AM to July 03 \~11:45 AM) 

**Summary:**

The portal code in the Portal Signin emails was displayed in a broken format, showing a placeholder instead of the second part of the code.

**Impact:**

Portal Signin users

**Root Cause:** 

On July 2nd, FS implemented styling changes to the Portal Signin email template. It appears that these changes were tested using placeholders instead of real values. Beside this, automated tests were successful even though the format was broken.

‌

**Action Items:**

A ticket has been created to add end-to-end tests for the portal sign-in process to check the code in the email [PL-47564: Portal Automation - Add portal code validation from ui in signin portal email](https://method.atlassian.net/browse/PL-47564)

Additionally, the team plans to emphasize manual testing with actual values to ensure thorough testing coverage.

‌

‌

### **Wednesday June 19, 2024**

**Incident/Alert:**

QBDT Real time sync from Method to QBDT file was down.

`(Ticket)`

**Prepared by (Author):**

[Michael Griffiths](mailto:m.griffiths@method.me)

**Duration:** 

\~ 45min - 8:50AM to 09:35 AM June 19th,, 2024

**Summary:**

QBDT Real time sync between Method->QBDT was down.  Would also show disconnected on Engine.

**Impact:**

All QBDT users

**Root Cause:** 

During deployment, it looks like the MethodTCPIPServer agent stopped operating.  This wasn’t deployed, a web service that calls it was. 

**Action Items:**

N/A - keep an eye on it, as deploying web service shouldn’t cause the agent any failure.

‌

‌

### **Monday June 03, 2024**

**Incident/Alert:**

Gmail Sidebar stopped working.  While you could sign in and see user information for the email itself.  None of the buttons worked.

`(Ticket)`

**Prepared by (Author):**

[Michael Griffiths](mailto:m.griffiths@method.me)

**Duration:** 

\~ 7.75hrs - 8:00AM to 15:45 AM June 3rd, 2024

**Summary:**

Gmail sidebar stopped working.

**Impact:**

All Gmail Sidebar users.

**Root Cause:** 

Looks like something on Google’s side.  While investigating it, it just started working again around 3:45 pm. We can’t find any status/ticket as to why/when this happened or what Google did.

**Action Items:**

N/A was a google issue.

### **Monday May 30, 2024**

**Incident/Alert:**

SOAP API calls from CIAMedical server had mysql count logging failure - due to timeout

`Failed to log a message, will not retry|MySql.Data.MySqlClient.MySqlException (0x80004005): error connecting: Timeout expired.  The timeout period elapsed prior to obtaining a connection from the pool.  This may have occurred because all pooled connections were in use and max pool size was reached.`

`(Ticket)`

**Prepared by (Author):**

[Michael Griffiths](mailto:m.griffiths@method.me)

**Duration:** 

\~ 37 mins - 8:49 AM to 9:26AM May 30th, 2024

**Summary:**

The CIAMedical box seems to be exhausting our connection pool with MySql.  Classic 4/5 had many users hitting it, but no effect.

**Impact:**

I believe this is minimal, it should only have had the error of updating the count for the api call, the api call itself should have been fine.  However they would most likely be subject to the lowest API account limit.

‌

_**Now confirmed, this wouldn’t have affected their API calls, it just means we failed to properly record all their calls, so they would get freebies on the amount of calls.**_

**Root Cause:** 

Sql connection failure (`The timeout period elapsed prior to obtaining a connection from the pool.  This may have occurred because all pooled connections were in use and max pool size was reached.`)

**Action Items:**

~~Attempting to increase pool size.~~ 

Calls to MySql made into a singleton.  Still strange, only happening on the CIAMedical server.  But now the noise is gone.

### **Monday May 27, 2024**

**Incident/Alert:**

Invoices - Email button on the New/Edit Invoice screen would send the email subject as the email body ([ticket](https://method.atlassian.net/browse/PL-47035))

**Prepared by (Author):**

Phil Côté

**Duration:**

\~6.5 hours (May 27 9:00 AM to May 27 \~3:30 PM) 

**Summary:**

A human error during the setting up of our releases resulted in the QBO US version of the New/Edit Invoice screen being reverted back incorrectly to version 403, which caused us to republish out the problematic version that was originally published on May 16th and caused this same issue earlier in the month (see below in this doc).

**Impact:**

Amplitude reporting on button menu clicks seems to be broken so don’t know the full impact, but this being a pretty common flow on a core screen, we can assume this impacted a significant number of users and accounts. 

The impact extends beyond just our customers; since this is an issue with the email button for the transaction if our users proceeded through the flow, the issue would have been experienced by their customers/recipients. The issue would have been apparent in the “preview” show message that appears, so our customers could have noticed and aborted the flow before actually sending the email, but I think it’s fair to assume that a high number of users would have proceeded past the preview message and may not have noticed.

Amplitude suggests this button was clicked 28 times across 12 accounts (but the real impact is likely higher than this).

**Root Cause:** 

Timeline:

1. May 15 - Version 403 of New/Edit Invoice is released, which releases this issue the original time, as part of [this](https://method.atlassian.net/browse/PL-46597) ticket (see below)
2. May 15 - Dev picks up [this](https://method.atlassian.net/browse/PL-46536) ticket from the backlog, and creates a new draft version 414 of New/Edit Invoice, off of the current live version 403. In the ticket as per the process, writes _“QBO version 403 → version 410”_
3. May 16 - The original instance of this P0 is picked up, a new version is created and hotfixed. The live version of New/Edit Invoice now went from 403 to 411. The fix is also applied to the draft version 414.
4. May 24 - Dev starts prepping a release for tickets that are in Done Test column. There is a ticket for changes on the New/Edit Invoice screen, and therefore starts the process of including this screen in the release. This release process today involves publishing the draft versions to Live in templatedevv2, so that on release day the app can just be published and the changes are released.   
  During this process however, the dev realized there were additional tickets that involved the New/Edit Invoice screen on these same versions of the screen that were still in “earlier” columns on the board, and therefore not ready to be released.   
  The dev therefore goes through the process of republishing the previously-live versions, to reset things back to how they were. They refer to the notes left on the tickets in order to identify which was the previous version. One of the tickets is the one mentioned above in #2; the dev sees the note that was originally left on it saying  _“QBO version 403 → version 410”_, and so republishes version 403.  
  There are still legitimate changes on other screens of the Invoices app that are kept in the pending release, scheduled for Monday May 27.
5. May 27 - The Invoices app is released, which inadvertently re-releases the P0 seen further below in this doc via the republished version 403 of New/Edit Invoice.

‌

**Action Items:**

1. Discussion within the team about this issue, along with the other recent ones. Acknowledgement and ownership of the issue is taken by the devs - a commitment is made to be more careful and precise moving forward. (Done ✅)
2. Immediate process changes

    1. Add the screen names to the end of the ticket titles on our board. Add a step to the process when setting up releases to use the searchbar on our board in Jira for the screen names that are potentially being included in the release, in order to more easily identify if there are other tickets elsewhere on the board that include changes on this same screen. (Should help prevent #4 in the timeline above) (Done ✅)
    
3. Potential future process/tool changes

    1. Consider asking for a specific field - or make use of some existing field - to keep track of the screen names, instead of using the ticket title as mentioned in 2.a.
    2. Request changes in templatedevv2 to make it easier to keep track of version changes, or reset to the previous live version
    
        1. Updates to the existing events logged in the Audit Trail under “App Management”: currently these logs just show that a new version has been published, and call out the new live version. Ideally, it would also mention the previous live version. “Screen X’s live version went from X to Y”, for example.
        
            1. This seems like the most obvious next step. **(**[**Ticket**](https://method.atlassian.net/browse/PL-47065) **created 🎫)**
            
        2. Maybe an explicit button “Reset to previous live version(s)”?
        3. A clearer log/history of the versions of a screen, outside of the Audit Trail? (Something kinda similar to the App Routine version log maybe?)
        
    3. Consider/discuss changes to the release process for Stock Apps
    
        1. As mentioned in #4 of the timeline above, when setting up a release today the process is to publish the candidate versions in templatedevv2, in Prod. Does this make sense? Should we instead publish them in Warehouse first? The changes would then go through automation the following day. If/when happy with the changes, the versions could _then_ be published in Prod, or maybe this should be done at the time of the actual release itself? Not sure if this change would have avoided the current issue altogether to be honest but it would at least add an extra safety layer between our dev environments and Prod.
        
    

### **Thursday May 16, 2024**

**Incident/Alert:**

Estimates - Email button on the New/Edit Estimate screen did not properly merge in the portal URL into the email body’s button ([ticket](https://method.atlassian.net/browse/PL-46904))

**Prepared by (Author):**

Phil Côté

**Duration:**

\~26.5 hours (May 15 9:00 AM to May 16 \~11:30 AM) 

**Summary:**

One of our bug fixes that went out the morning of Wednesday May 15 had a mistake on the QBO Global version, where the Portal URL was no longer properly being merged into the button featured in the email body.

**Impact:**

Amplitude reporting on button menu clicks seems to be broken so don’t know the full impact, but this being a pretty common flow on a core screen, we can assume this impacted a significant number of users and accounts (the saving grace might be that it was only an issue for QBO Global).

The impact extends beyond just our customers; since this is an issue with the email button for the transaction if our users proceeded through the flow, the issue would have been experienced by their customers/recipients.

Amplitude suggests this button was clicked 22 times across 5 accounts (but the real impact is likely higher than this).

**Root Cause:** 

An action that was inadvertently removed on the QBO Global version of the New/Edit Estimate screen that got shipped on the morning of May 15. 

‌

**Action Items:**

4. Given the other P0, the team will go through all the New/Edit transaction screens and thoroughly re-test all the email buttons, to confirm no other issues were missed. (Done ✅)
5. Given the other P0, discussion with the Stock Apps team to understand why these mistakes are happening during dev and what we can do to avoid them. (Done ✅)
6. Discussion with the Stock Apps team to understand how this was missed during peer review. (Done ✅)

    1. From the discussion, learned that the peer review process was maybe not as thorough as it could have been. Previous process was to review the resolution details on the ticket and just confirm that the logic was sound. New process moving forward is to continue to do that, but also go into the editor and review the “code” in more detail to re-confirm that the logic is sound now within the context of the existing screen logic, and also to catch these types of mistakes. (Done ✅)
    
7. Discussion with the Stock Apps team to understand how this was missed during testing. (Done ✅)

    1. Unlike the issue below, this issue was not directly related to the change in question, so that’s why it wasn’t caught during testing. Agreed to try and be more thorough with testing in the future and do our best to test even parts of the flow/feature that are not entirely, directly related to the change at hand but somewhat adjacent. (Done ✅)
    2. Discussion to confirm whether Manu and QA only should test tickets moving forward (In Progress 💬)
    
8. Discussion with Stock Apps QA to see whether we might want to add automation coverage here.

### **Thursday May 16, 2024**

**Incident/Alert:**

Invoices - Email button on the New/Edit Invoice screen would send the email subject as the email body ([ticket](https://method.atlassian.net/browse/PL-46893))

**Prepared by (Author):**

Phil Côté

**Duration:**

\~22 hours (May 15 9:00 AM to May 16 \~7:00 AM) 

**Summary:**

One of our bug fixes that went out the morning of Wednesday May 15 had a mistake on the QBO US version, where an action result for the email subject was being resaved as the email body.

**Impact:**

Amplitude reporting on button menu clicks seems to be broken so don’t know the full impact, but this being a pretty common flow on a core screen, we can assume this impacted a significant number of users and accounts. 

The impact extends beyond just our customers; since this is an issue with the email button for the transaction if our users proceeded through the flow, the issue would have been experienced by their customers/recipients. The issue would have been apparent in the “preview” show message that appears, so our customers could have noticed and aborted the flow before actually sending the email, but I think it’s fair to assume that a high number of users would have proceeded past the preview message and may not have noticed.

Amplitude suggests this button was clicked 50 times across 15 accounts (but the real impact is likely higher than this).

**Root Cause:** 

An incorrectly configured action on the QBO US version of the New/Edit Invoice screen that got shipped on the morning of May 15. 

‌

**Action Items:**

1. Discussion with Inder and Mike Melo about ways we can be notified of issues like these earlier, and/or bumping to P0 earlier. (Done ✅)
2. Discussion with the Stock Apps team to understand how this was missed during peer review. (Done ✅)

    1. From the discussion, learned that the peer review process was maybe not as thorough as it could have been. Previous process was to review the resolution details on the ticket and just confirm that the logic was sound. New process moving forward is to continue to do that, but also go in and review the “code” in more detail to re-confirm that the logic is sound now within the context of the existing screen logic, and also to catch these types of mistakes. (Done ✅)
    
3. Discussion with the Stock Apps team to understand how this was missed during testing. (Done ✅)

    1. Acknowledgement and ownership by the tester that they made a mistake with this ticket and will be more thorough in the future. Admits that this 100% should have been caught at this stage. (Done ✅)
    2. Discussion to confirm whether Manu and QA only should test tickets moving forward (In Progress 💬)
    
4. Discussion with Stock Apps QA to see whether we might want to add automation coverage here. 

‌

### **Friday May 03, 2024**

**Incident/Alert:**

Getting 404 opening report designer (for specific users/accounts) ([ticket](https://method.atlassian.net/browse/PL-46633))

**Prepared by (Author):**

Greg Hitchon

**Duration:**

\~53 minutes (2:00 PM to 2:53 PM) 

**Summary:**

We rolled out a HF (method-ui) which caused some 404 errors when accessing report designer.

**Impact:**

A few known customer accounts.

**Root Cause:** 

The root cause is not entirely clear. Additional analysis in the original ticket [here](https://method.atlassian.net/browse/PL-46410). Summary: there were a few errors looked to be unique and related to configuration. The code changes were unrelated (it would seem) and not reproducible on dev environments. Was working for certain users on a specific account and not others. Seemed to be some transient or ALB related non-deterministic behavior.

‌

UPDATE: the root cause is still not completely resolved, however releasing the same code resulted in no issues. The code was in a completely unrelated area and the error logs indicate some kind of corruption occurred in the config files or generally in the copy. 

‌

**Action Items:**

1. ~~Try to repro on WH (Update: was not able to)~~
2. ~~Try to repro on prod using appx (Update: was not able to)~~
3. ~~Try re-releasing off hours and monitor for similar issue (Update: we did not see similar issues when re-releasing. This indicates that we had some kind of glitch with the release that caused some config corruption which caused report designer to break)~~
4. Devops/release investigation into pipeline

‌

### **Thursday April 11, 2024**

**Incident/Alert:** 

Trouble loading Dashboard

**Prepared by (Author):**

Aqueel / Greg

**Duration:**

11:10 AM to 11:30 AM

**Summary:**

Around 11:10 AM we had an issue with MSL03 where the machine became unresponsive and we received multiple alerts in the alert channel (health checks failing). Upon investigation the MSL03 box had failed after a spike in CPU and memory within apps microservice. Restarting the box resolved the issue and the memory issues did not return.

**Impact:**

Users were unable to login for around 10 minutes (from when the box failed to when it was removed from load balancer). 

**Root Cause:** 

Unknown

**Action Items:**

1. Look into root cause 

‌

### **Friday April 5, 2024**

**Incident/Alert:**

Trouble logging into Method

**Prepared by (Author):** 

Aqueel

**Duration:**

9:00 AM to 9:10 AM

**Summary:**

At the time of Today’s morning release of the project ms-account-api, around 9 AM; the release process drains one instance at a time, deploys the code and moves to another instance of the target group. During this period, for the microservice ‘account’ there were many open files trying to access which caused it to not respond completely. This resulted in health checking failing and the services dependent on ‘account’ microservice also failed.

**Impact:**

Users had trouble logging into Method, once logged in, the application was slow to respond.

**Root Cause:** 

The nginx service which handles the connections to the linux boxes has a limit of max connections of 1024, also there are other microservices on the same machine also trying to use the resources.

**Action Items:**

* [Aqueel Rahman](mailto:a.rahman@method.me) to increase the soft limit on connections for nginx
* DevOps - to plan on adding an extra node for MSL box
* Developers - Cut down on calls to ms-account from method:ui
* [Richard Pangborn](mailto:r.pangborn@method.me)/[Arash Pakbaz](mailto:a.pakbaz@method.me) to schedule application health review meetings with Development teams.

### **Wednesday April 3, 2024**

**Incident/Alert:**

Some customers were unable to access Method at around 3:40PM

**Prepared by (Author):**

Arash

**Duration:**

3-5 minutes

**Summary:**

At around 3:07 PM, the method-ui application pool failed to read its configuration file, prompting an attempt to recycle the app pool. This recycling process appears to have been successful.

Subsequently, at 3:35 PM, based on our log analysis and Centreon monitoring, the server encountered an out-of-memory exception, which resulted in the application pool being stopped. It should have restarted automatically afterward.

While the target group was attempting to reroute traffic to another server, we experienced a brief out-of-memory issue there as well. However, this server managed to stay operational,  with approximately 30 error counts reported in Logstash.

New5 remained healthy throughout this period but was unable to handle the increased load effectively.

**Impact:**

Most customers but not all

**Root Cause:** 

Out of memory on New5 and New6

**Action Items:**

‌

‌

### **Tuesday April 2, 2024**

**Incident/Alert:**

[**Email Preferences - Emails going to spam from notifications@mail.method.me**](https://method.atlassian.net/browse/PL-46100)

**Prepared by (Author):** [**Gregory Hitchon**](mailto:g.hitchon@method.me)

**Duration:**

\~24 hours (April 1st 11:30 AM to April 2nd 11:00 AM

**Summary:**

Due to a rather particular set of circumstances (see ticket) emails sent from alocetsystem (not from a system email) were going through the fallback email and due to the default domain on the parent sendgrid account were being flagged as spam.

**Impact:**

Users may have had a variety of emails (receipts, case updates, etc.) go to spam

**Root Cause:**

Lack of manual/automated testing on alocet, and hardcoded exceptions in architecture

**Action Items:**

N/A

‌

### **Thursday March 28, 2024**

[**Real time sync between Classic web users and the engine was down **](https://method.atlassian.net/browse/PL-46046)

**Prepared by (Author):** [**Michael Griffiths**](mailto:m.griffiths@method.me)

Duration: 12hr (\~ March 27, 10.30 PM ET to \~March 28, 10:20 AM ET) 

**Summary:**

Classic web users, if saved in Method, didn’t go real time sync to their QBDT file.

**Impact:**

Only for classic Method UI web users, would they find any changes in method wouldn’t sync directly to their QBDT file.  They’d have to wait \~15-20 mins for background engine sync to pick it up.  Method New uses weren’t impacted.

**Root Cause:** 

Connection issue between classic website 4/5 to legacy-syncservice-api.

**Action Items:**

Look into if we have to use public IP’s instead of NAT.  Also connection issue between classic and new MethodTCPIP server.

‌

### **Tuesday March 19, 2024**

**Incident/Alert:**

[**Issues sending to Yahoo! from authenticated domains**](https://method.atlassian.net/browse/PL-45894)

**Prepared by (Author):**

Greg Hitchon

**Duration:**

\~720 minutes

**Summary:**

Identified an issue where emails sent to yahoo and aol addresses are not being delivered. Caused by majesticturbodallas sending several large (\~10-20k recipient) email campaigns on March 19th. Resulted in IP address being flagged by yahoo for higher than normal volume. IP warm-up was not sufficient for this volume. Temporary flag we assume. 

**Impact:**

For users with authenticated domain (about 30 users) any emails sent to <custom data-type="smartlink" data-id="id-56">http://Yahoo.com</custom>  recipients would be delayed a number of hours

**Root Cause:** 

IP warmup not long enough/not successful

**Action Items:**

1. Confirm existing alerting/monitoring setup
2. Test .74 and .137 IP’s to ensure issue is resolved, restart warmup
3. Look into email address validation
4. Talk to the account that had issues and provide them info on best practices/unsubscribe/volume
5. Monitor SendGrid

‌

### **Wednesday March 13, 2024**

**Incident/Alert:**

[**Authenticated Domains: not all emails are sending properly from sub-user**](https://method.atlassian.net/browse/PL-45779)

**Prepared by (Author):**

Greg

**Duration:**

148 minutes

**Summary:**

Prior to widespread communication some users had authenticated domains and were using them to send mail. During monitoring we noticed that some of the emails were not being authenticated and going through the incorrect sub-user.

This led to a further investigation which found an old service had come to life during some patching work and so instead of 4 valid subscriber agents there were 5 total (4 valid and 1 invalid).

This led to \~20% of traffic going to the incorrect sub-user.

**Impact:**

Users may experience those 20% of mail going to spam, or at a higher rate. Additionally it is possible they tried testing the new feature and during testing noticed inconsistency.

**Root Cause:** 

The old service on linux-prod-1 and 2 was disabled and removed from the service catalog but for some reason after the restart it was reinstated. 

‌

**Action Items:**

‌

We have removed the code and service.

‌

‌

### **Thursday Feb 29, 2024**

**Incident/Alert:**

[**Real time sync from Method -> QBDT was down **](https://method.atlassian.net/browse/PL-45596)

**Prepared by (Author):** [**Michael Griffiths**](mailto:m.griffiths@method.me)

Duration: 12hr (\~Thursday April 29, 10 PM ET to \~March 1, 10 AM ET) 

**Summary:**

DNS entry to utility-prod server was incorrect/changed. 

**Impact:**

Real time sync between Method -> QBDT was down.  And on the Method Integration Engine users would see connection failure.  However sync still worked (background every 15 minutes as well)  Minimal impact on what's happening, but visually may alarm users.

**Root Cause:** 

DNS entry was incorrect

**Action Items:**

Incorrect IP address as one of DNS entries.  This was fixed, nothing left to do.

‌

‌

### **Wednesday Feb 28, 2024**

**Incident/Alert:**

[**Customized Screen - Custom Screen loads blank - Cannot Read Properties of null (reading ' getBoundingClientRect') **](https://method.atlassian.net/browse/AS-11505)

**Prepared by (Author):** [**Alexander Ballard**](mailto:a.ballard@method.me)

Duration: 6hr (\~9:15 AM ET to \~3:00 PM ET) 

**Summary:**

A change to the gallery component meant that screens with hidden gallery components failed to load.  

**Impact:**

Only affected one customer that we know of.  Gallery is a rarely used component so impact was minimal.

**Root Cause:** 

Code change

**Action Items:**

Additional checks added to components to prevent the bug in the future.

**Incident/Alert:**

[**Payment process issue - "BOLT-1178 Sorry, we are currently unable to process your payment due to a technical issue" error message**](https://method.atlassian.net/browse/PL-45556)

**Prepared by (Author):**

Greg hitchon

**Duration:**

6hr (\~9:15 AM ET to \~3:00 PM ET)

**Summary:**

We were notified by customer England Logistics that payments were failing. Upon investigation a Shuttle release had caused issues with this specific account

**Impact:**

Payments failed for this account, high business impact

**Root Cause:** 

Unique configuration and bad QA on Shuttle side

**Action Items:**

1. All captured in fortify plans

‌

‌

‌

### **Wednesday Feb 14, 2024**

**Incident/Alert:**

[\[AS-11480\] Communications - Method Server Emails stuck in Processing Status - JIRA (atlassian.net)](https://method.atlassian.net/browse/AS-11480)

Emails were not being sent out

**Prepared by (Author):**

[**Arash Pakbaz**](mailto:a.pakbaz@method.me)

**Duration:**

‌

**Summary:**

On February 2nd, we implemented changes to enhance email deliverability. However, a minor issue arose: when the batch_id was set to null, the system failed to select the appropriate records from the table.

**Impact:**

minimal, delay sending emails for 5 or 6 customers but nothing was lost.

**Root Cause:** 

‌

**Action Items:**

A hotfix were pushed [#AS-11480 fix an issue with bulk query by apakbaz · Pull Request #65 · methodcrm/legacy-email-agent (github.com)](https://github.com/methodcrm/legacy-email-agent/pull/65/files)

‌

### **Monday Feb 05, 2024**

**Incident/Alert:**  
App Routines: Screen Not Loading Correctly

<custom data-type="smartlink" data-id="id-57">https://method.atlassian.net/browse/AS-11450</custom>  

**Prepared by (Author):**

[**Elliot Ruiz**](mailto:e.ruiz@method.me)

**Duration: \~ 10 mins**

At 9:36 AM to 9:45 AM

**Summary:**

We've received reports from customers about an issue with the app's routine screen. Some users have encountered a problem where the screen shifts completely to the left, preventing them from saving or closing it.

‌

**Impact:**

Users accessing the app routine action sets screen could have experienced the same issue. While we don't have an exact number of reports, the support team has informed us that a fair number of users encountered this issue.

‌

**Root Cause:** 

The code changes made for this ticket (<custom data-type="smartlink" data-id="id-58">https://method.atlassian.net/browse/PL-42724</custom> **)** didn’t account for the app routine action sets screen, making it shift to the left since it didn’t let the screen load the styles correctly.

**Action Items:**

Return original ticket to impact’s backlog and take into account the app routine’s action sets screen that was having issues

‌

‌

‌

### **Thursday Jan 25, 2024**

**Incident/Alert:**

At 7:48 PM, alerts started pouring in the #alert-system channel. The alerts were raised by Grafana, which is the Logstash4 machine. All the alerts were a type of DatasourceError.

**Prepared by (Author):**

[**Aqueel Rahman**](mailto:a.rahman@method.me)

**Duration: \~ 15 mins**

7:48 PM to 7:59 PM

8:23 PM to 8:28 PM

**Summary:**

Network connection from the Logstash4 machine timed out, this caused Grafana to throw the alerts.

**Impact:**

No customer impact as this was a logging/monitoring machine.

**Root Cause:** 

From logs, 

`Jan` `25` `00:32:01` `logstash4.method.local` `systemd-timesyncd[560]:` `Network` `configuration` `changed,` `trying` `to` `establish` `connection.`

`Jan` `25` `00:32:01` `logstash4.method.local` `systemd-networkd[758]:` `ens5:` `Could` `not` `set` `DHCPv4` `address:` `Connection` `timed` `out`

`Jan` `25` `00:32:01` `logstash4.method.local` `systemd-networkd[758]:` `ens5:` `Failed`

`Jan` `25` `00:32:07` `logstash4.method.local` `systemd-timesyncd[560]:` `Synchronized` `to` `time` `server` `172.31.7.31:123` `(172.31.7.31).`

`Jan` `25` `00:33:18` `logstash4.method.local` `systemd-networkd[758]:` `ens5:` `Could` `not` `set` `DHCPv4` `route:` `Connection` `timed` `out`

`Jan` `25` `00:33:23` `logstash4.method.local` `systemd-networkd[758]:` `ens5:` `Failed`

‌

**Action Items:**

N/A

‌

---

‌

‌

### **Friday Jan 19, 2024**

**Incident/Alert:**

Shuttle portal not responding and payments do not seem processed since 1:40 EST

<custom data-type="smartlink" data-id="id-59">https://methodme.slack.com/archives/C01L5K42GQ6/p1705692387287519</custom> 

‌

**Prepared by (Author): Sammy**

‌

**Duration: \~ 1 hour - 1.5 hour**

‌

**Summary:**

**We experienced an outage from Shuttle in the following areas**

* **Payment Widget** 

    * **Did not render payment widget, 504 gateway timeout black screen**
    
* **Shuttle Dev Portal** 

    * **Unable to successfully log in**
    
* **Setup Account creation**

    * **Unable to create/edit a shuttle instance from system outage**
    
* **Webhooks**

    * **Did not receive any during the outage**
    
* **Api** 

    * **API returned 500 internal server error response code**
    

‌

**Impact:**

**Was unfortunately impacted from all fronts, customers would have experienced the 504 gateway if using the payment widget during the affected time. Any other requests which use the API were also likely affected during this time.** 

‌

**Root Cause:** 

**Response from Shuttle:**   
_we have alot of investigating still to do, but for a critical component what appears to have happened if traffic to a specific datacenter was intermittently failing. We have disabled that data center for now while we investigate why. We haven’t made any changes our side, and these are all using managed components._

_I’m hoping AWS flag a general issue their side, otherwise it might just be related to our specific environment, eg one of their load balancers went bust in a region._

_we will do a full investigation_

‌

**Action Items:**

**We got some initial notifications in the alert channel due to timeout and api errors, but discussing other ways to look into alerting if we’re not getting notifications over a longer stretches of time that deviate from the norm**

‌

‌

### **Tuesday Jan 16, 2024**

**Incident/Alert:**

[Chrome on Windows: Screen Editor - Cannot View Properties/Action Sets of Screen Controls](https://method.atlassian.net/browse/PL-44761)

**Prepared by (Author):**

Greg Hitchon

**Duration:**

1 day

**Summary:**

New Chrome release broke (sporadically) the designer completely.

**Impact:**

No known customer impact.

**Root Cause:** 

Issue with the way designer loads templates which was fine until latest Chrome release.

**Action Items:**

N/A

### **Wednesday Dec 13, 2023**

‌

**Incident/Alert:**

App update did not pick up some changes which were required for a Stock Apps release to work effectively ([ticket](https://method.atlassian.net/browse/PL-44464)))

**Prepared by (Author):**

Greg Hitchon

**Duration:**

TBD

**Summary:**

A column was not properly added to all accounts. TBD whether this is an app update issue or a process issue

**Impact:**

3 customers experienced broken screen (drop down wont load)

**Root Cause:** 

Stock Apps needed to ask Impact to set defaults ahead of time, but would have expected the field to still have gone out to all accounts.

IsAvailableforReorder in ItemTable is the problem field in question. Field was set as a filter criteria in a  dropdown. Expectation is that any new field referenced on a screen should be created as part of App Update. Possibly gaps - does the field need to actually be included on the screen in order to be created. 

App Update process wasn’t tested as part of dev process; field was manually added to table as part of testing process. QA on this ticket was done on the same account that had dev testing, so did not go through app update. 

‌

Anytime Stock Apps is adding a new field, they are manually adding it for dev testing. Not sure what QA team was doing when full time QA was here (Stock Apps devs have been QA-ing in the interim). Stock Apps devs should NOT be manually adding columns in these instances. 

‌

The issue may have arisen during QA process (unclear), but was ignored as part of general stock apps inconsistency in the app update process. These instances should be treated as high priority and escalated to Impact ASAP so stock apps tickets can be tested fully. 

**Action Items**

* Hannah Johnston Return to ticket on original App Update issues that was closed - should be further investigated and treated as priority by Impact.
* Phil Cote Create follow up ticket for App Updates when field is not on the screen. Stock Apps Manifesto should also be updated to document what works currently and what is not supported.
* Phil Cote Clarify QA and testing process for Stock Apps changes that include new field creation. Doesn’t seem that App Updates are being tested properly.

‌

‌

‌

### **Friday Dec 8, 2023**

‌

**Incident/Alert:**

[Microsoft SSO Sign in Issue / Microsoft secret keys expiration](https://method.atlassian.net/browse/PL-44416)

**Prepared by (Author):**

[**Gozde Bulut**](mailto:g.bulut@method.me)

**Duration:** 

\~ 9 hours (2:30 AM to 11:30 AM)

**Summary:**

Users were not able to sign in with Microsoft SSO during this period

**Impact:**

Only whitelisted users. Based on the IP addresses that we can see in the logs,  potential \~ 6 affected accounts

**Root Cause:** 

Microsoft SSO secret keys expiration that we have not had any notification about earlier

**Action Items:**

* Arash helped to create new Microsoft secret keys, added them in the Secret Manager
* It seems that we could only create Microsoft keys with 2 years expiration date so the team will look into put a reminder on this to not have the same issue next time
* FS team to look into creating up-to-date doc regarding SSO details and secret keys
* QA team to ensure we run Sign in SSO automation tests daily

‌

### **Monday Dec 4, 2023**

‌

**Incident/Alert:**

[Performance - Screens loading really slow related to redis](https://method.atlassian.net/browse/PL-44333)

**Prepared by (Author):**

[Gregory Hitchon](mailto:g.hitchon@method.me)

**Duration:**

\~ 20 minutes (8:55 AM to 9:15 AM)

**Summary:**

There was a code change which was meant to protect against an edge case MT issue. Within a conditional there was a cache clear which was meant only rarely to be executed. In fact it seems like this case was more common and the cache clear happened frequently. This led to an increase in redis size and slowed down the platform.

**Impact:**

User reported slow load times after release.

**Root Cause:** 

1. Dev should have done more analysis to ensure edge case was indeed low frequency
2. Should have been caught in review (to ensure #1)
3. No load testing meant that was not able to be discerned in QA

‌

**Action Items:**

1. QA to look into more comprehensive load testing
2. All teams to flag architects more liberally when dealing with areas they are unsure about or high risk

‌

‌

---

‌

### **Friday Dec 1, 2023**

‌

**Incident/Alert:**

Ms-account-api on msl-03 failed to 

**Prepared by (Author):**

[Aqueel Rahman](mailto:a.rahman@method.me)

[Arash Pakbaz](mailto:a.pakbaz@method.me)

**Duration:**

\~ 14 minutes (9:04 AM to 9:18 AM)

**Summary:**

Method was slow to respond, it took about 30 seconds to load the screen.

**Impact:**

The impact was not much, a repeated reload of screen was able to load the page correctly.

**Root Cause:** 

Looking at the logs on MSL-03 and TFS ansible, it looks like ms-account health check passed with 200 response code during the release and there was no issues and the service was put back into the target group in AWS, the following log is from nginx on MSL-03

| 172.31.94.57 - - \[01/Dec/2023:14:04:30 +0000\] "GET /account/health/check HTTP/1.1" 200 1393 "-" "ansible-httpget" "-" |
| --- |

‌

But further analysis of ms-account logs revealed that the service immediately failed to query Redis due to timeout, started at Dec 01 14:05:04 UTC. 

‌

| Dec 01 14:05:04 ip-172-31-94-57 account\[24466\]: StackExchange.Redis.RedisConnectionException: It was not possible to connect to the redis server(s). Error connecting right now. To allow this multiplexer to continue retrying until it's able to connect, use abortConnect=false in your connection string or AbortOnConnectFail=false; in your code. Dec 01 14:05:04 ip-172-31-94-57 account\[24466\]:    at StackExchange.Redis.ConnectionMultiplexer.ConnectImplAsync(ConfigurationOptions configuration, TextWriter log, Nullable\`1 serverType) in /\_/src/StackExchange.Redis/ConnectionMultiplexer.cs:line 609 Dec 01 14:05:04 ip-172-31-94-57 account\[24466\]:    at Method.Core.Caching.Redis.RedisCache.ConnectSlowAsync(CancellationToken token) Dec 01 14:05:04 ip-172-31-94-57 account\[24466\]:    at Method.Core.Caching.Redis.RedisCache.GetStringAsync(String key, CancellationToken token) |
| --- |

‌

I believe the way that we check Redis during health check is just sending a \`ping\` message and not actually asking for a key, eventhough that \`ping\` command is pretty common to check Redis health but this happens in future we need to do some refactoring on our health check. 

For reason as to why it failed to connect to redis with a timeout, I created a ticket to modify the nuget to have better error handling.

**Action Items:**

Updated the health check on AWS to call on “/health/check”, as earlier it was just “/health/heartbeat”

<custom data-type="smartlink" data-id="id-60">https://method.atlassian.net/browse/PL-44270</custom> 

[\[PL-44341\] ms-account improve caching timeout and retries - JIRA (atlassian.net)](https://method.atlassian.net/browse/PL-44341)

‌

‌

---

‌

‌

### **Wednesday Nov 29,2023**

‌

**Incident/Alert:**

At 8:54 AM, during tables-fields release, Yuri noticed that deployment was failing on healthcheck, and at the same time, Mike Melo and others noticed some errors initially related to tables-fields popping up in logstash. A few minutes later in the slack channel, a swat created complaining that tables-fields pages were not loading, and later complaints were related to the designer app and other tables-fields-related apps. We took a look at the health checks and noticed MSN02 health check is failing on tables-fields (error captured in the following ticket) although MSN01 was healthy. Meanwhile, Yuri wasn't able to roll back the code. At 9:07 AM as Arash suggested, Aqueel recycled the app pool and Yuri was able to roll back and everything back to normal. 

‌

**Prepared by (Author):**

[Aqueel Rahman](mailto:a.rahman@method.me)  
[Arash Pakbaz](mailto:a.pakbaz@method.me)  
[Matt Pourasadi](mailto:m.pourasadi@method.me)  
**Duration:**

\~13 minutes (8:54 AM to 9:07 AM)  
**Summary:**

Matt and Aqueel initially investigated Application Event Logs on MSN02 and noticed that the same error on Tables-Fields api calls and health check started showing up on ms-archive-api from Monday Nov 23 and at the same time no logs or activity from ms-archive-api on MSN02  from Nov 23 till Nov 29 although heartbeat/health check was green all these days. Aqueel mentioned that the night before on Nov 22 he patched Windows on MSN02 with some patching for .Net Framework but did not restart the server. So we think it may be related to the patching but it is under investigation.   
**Impact:**

Screen designer/Customize Screens was unresponsive with reports from Errol, Inder, Nelson and Micheal Melo. 

**Root Cause:** 

Current speculation is after the windows patching, the app pools required a recycle or a restart. There might be a good chance the machine also needed a reboot.  
**Action Items:**

The monthly patching is paused as of now. The steps will be revisited to accommodate the auto recycle/restart of app pools, if possible also an extra step to reboot the target machine.

<custom data-type="smartlink" data-id="id-61">https://method.atlassian.net/browse/PL-44252</custom> 

‌

‌

‌

---

‌

### **Monday Nov, 27 2023**

**Incident/Alert:**

At 1:46 PM, a message in SWAT channel by Nelson pointed the unresponsive nature of Method services.

**Prepared by (Author):**

[Aqueel Rahman](mailto:a.rahman@method.me)  
[Arash Pakbaz](mailto:a.pakbaz@method.me)

**Duration:**

\~4 minutes (1:46 PM to 1:49 PM)

**Summary:**

Seems like if a customer causes the audit trail to max out the system has errors and audit trail entries are lost. The queue was getting overwhelmed with messages, and the service could not process requests thus going into Critical condition.

**Impact:**

2 customers reached out to Nelson (one via email, other via chat)

**Root Cause:** 

By looking at the logs it seems that RabbitMQ nodes were unable to connect to each other.

| 2023-11-27 18:44:24.650314+00:00 \[error\] <0.15237.0> \*\* Node 'rabbit@ip-xxxxx' not responding \*\* 2023-11-27 18:44:24.650314+00:00 \[error\] <0.15237.0> \*\* Removing (timedout) connection \*\* |
| --- |

‌

Linux-prod-01 was suffering from high memory usage and failed.   
AuditTrail was triggered by qbo-sync-api which was syncing to pull a customer’s more than 50K changes mostly related to accTaxClassification updates in a very short period of time. Although AuditTrail could process a hundred times faster than QBO Sync (like processing 50K messages in half a minute), an issue was slowing the update on the ElasticSearch side that was causing messages to be piled up and reach to 20K limit that could cause rabbitMQ message loss. So as a workaround, we needed to audit.trail queue three times to the temporary queues to prevent message loss. 

‌

**Action Items:**

<custom data-type="smartlink" data-id="id-62">https://method.atlassian.net/browse/PL-44203</custom> 

‌

‌

‌

‌

‌

---

‌

‌

### **Thursday Nov, 22 2023**

**Incident/Alert:**

Issue with iOS users with customization on text input onFocus causing keyboard not to open. [Ticket](https://method.atlassian.net/browse/PL-44055)

**Prepared by (Author):** 

[Gregory Hitchon](mailto:g.hitchon@method.me)

**Duration:**

 \~1 day

**Summary:**

There was an issue impacting iOS users (v17+) where the text input was not opening the keyboard on mobile. This was caused by a change in the OS and how controls respond to being disabled. This was an issue that was opened as a P2, might be useful to discuss why it was not escalated earlier.

**Impact:**

High impact to a few accounts with customization on these inputs

**Root Cause:** 

No pro-active testing for major known OS updates

**Action Items:**

Organizational policy improvements in terms of testing (discussed during L10 and to be championed by [John Jones](mailto:j.jones@method.me))

‌

### **Wednesday Nov, 16 2023**

‌

**Incident/Alert:**

At around 10 am, some users started experiencing issues generating reports.

**Prepared by (Author):**   
[Arash Pakbaz](mailto:a.pakbaz@method.me)

**Duration:**

10 min.

**Summary:**

When the new report machine was put to receive 100% traffic, after a while customer started seeing errors when generating reports. 

**Impact:**

In total 60 customers were affected. 

**Root Cause:** 

Even though we gradually increase the traffic to the new machines but for some reason when we put 100% of the traffic the app pool failed and stopped on one of the machines. Also AWS target group health check was not correct not to send the traffic to the faulty machine. 

**Action Items:**

Those two machines were removed from the load balancer and further investigation revealeved the app pool failed.   
More tests will be done before the next try to identify the cause. 

‌

‌

---

‌

### **Wednesday Nov, 15 2023**

‌

**Incident/Alert:**

[Ticket](https://method.atlassian.net/browse/PL-44065): At around 8:30 AM Shuttle released some changes which caused payments to fail. 

**Prepared by (Author):**   
[Gregory Hitchon](mailto:g.hitchon@method.me)

**Duration:**

2 hrs

**Summary:**

Shuttle released changes that caused payments to fail. Customers could not complete transactions and Method was logging E008 reference set to null exceptions. 

**Impact:**

Customers could not use payments and were unable to complete transactions. Further investigation is required however it seems to have only impacted certain accounts.

**Root Cause:** 

Bad release from Shuttle, still awaiting further details.

**Action Items**

Ticket already in progress to address issue from our side (linked in parent ticket).

‌

---

‌

### **Thursday Nov, 9 2023** 

‌

**Incident/Alert:**

At approximately 9:40 am, we started receiving alerts on #alert-system channel with services going into Critical condition. Most of the prod instances were firing and the services on these instances were Critical. Method was not accessible from 9:45 AM to 11:30 AM.

‌

**Duration:**

1h 45 mins

‌

**Summary:**

What started as a chain reaction of service unavailability, made the Dashboard on Method UI inaccessible to users. Initial investigation showed RabbitMQ was getting hit with messages making it become unresponsive. This inturn made the prod linux boxes prod-linux-01 and prod-linux-02 criticaland unresponsive. Initial reboots of the linux boxes made the RabbitMQ service stable, but it was going into Critical condition in no time.

‌

**Impact:**

All users accessing Dashboard were initially seeing blank white screen. The gateway and api were returning 502 - Bad Gateway and 503 - Service Unavailable error. 

‌

**Root Cause:** 

The investigation and analysis at this point is not complete to point to the root cause that triggered the outage. Even after restarting prod-linux boxes the situation was not getting controlled. Method was brought down by shutting down the major prod instances (MSL03/04, MSN01/02, NEW5/6) for approximately 10 minutes. On the other hand, one speculation arose when today’s release with ms-preferences-api had a rough release on TFS, in the midst of the outage, a rollback was attempted but was not successful. 

‌

Upon examination of the operating system logs, it was observed that at approximately 9:52 AM, the 'email-subscriber' process was forcibly terminated by the operating system as a result of excessive memory consumption. However, it appears that prior to this termination, the RabbitMQ service had already experienced a failure. This failure occurred despite the expected failover mechanism to an alternate node. The malfunction in the failover process was likely due to the secondary node experiencing a deficiency in available memory resources.

‌

**Action Items:**

After all the major prod instances were stopped and started again, the services were getting back to normal. Also, the prod-linux-01 and prod-linux-02 instances were upsized to t3.xLarge. Later, a complete rollback was done on today’s release and further releases and merges are paused on following projects

* method-platform-ui
* event-subscriber-audittrail
* mobile-notifications-stack
* ms-audittrail-api
* ms-preferences-api
* new-import-stack

Further investigation and analysis is required to be done on 

* [api.method.me](http://api.method.me)
* rabbit mq cluster
* email subscriber service
* MethodUI 

‌

A new cluster of Ubuntu machines (prod-svc-01, prod-svc-02) will be created on AWS to host email-subscriber and email-publisher and later on gateway and oauth projects keeping prod-linux boxes only for rabbitmq. 

‌

---

‌

### **Wednesday Nov, 1 2023** 

‌

**Incident/Alert:**

At approximately 10:15 am, [an alert](https://methodme.slack.com/archives/CPHHABKAA/p1698848124279659) was triggered indicating that the legacy-syncservice was down. This was then followed by a [SWAT notification](https://methodme.slack.com/archives/C01L5K42GQ6/p1698847982709779) indicating users encountered error messages **WEB-1698847758266** and **WEB-1698847826669** within the platform.

‌

**Duration:**

148 minutes in total but 20 mins for Classic users not being able to access the platform.

‌

**Summary:**

There were challenges accessing both platforms, especially in sections that interfaced with sync. The initial remediation involved stopping the eventssubscriberssync.service in msl 3/4, as it was hammering syncservices on classic 4/5.   
Several solutions were considered. 

* A patch was applied to the eventssubscriberssync project to restrict sync calls to \`acc\` tables, but this did not alleviate the problem. 
* Additionally, flushing cache entries in Redis proved ineffective. 
* The final solution was the restart of the MethodTCPIP service. 
* Manual recycle of the app pools on classic 4 and 5 to help alleviate
* We also observed a significant number of messages in the queue associated with tables that do not require sync.

‌

**Impact:**

All users of the Classic platform (for 20 mins) and a subset of MethodNew users experienced disruptions, especially those dependent on real-time sync.

‌

**Root Cause:** 

The morning release, which included an update to the dotnet framework for the sync services, might have instigated the issue. This update probably prevented the service from initializing properly, potentially leading the MethodTCPIP service to hang. This could be due to restricted threads or connections, limiting its request-handling capability. A restart restored normal functionality.

‌

**Action Items:**

‌

1. [Matt Pourasadi](mailto:m.pourasadi@method.me) found [a bug](https://method.atlassian.net/browse/PL-43784?atlOrigin=eyJpIjoiNjQ2ZDUyNjVjZWZjNDNmMmFhZjRhOGM1YjE2NWVhZTEiLCJwIjoiamlyYS1zbGFjay1pbnQifQ) during the investigation of this issue regarding the way DAL should prevent Sync and provided the fix and verified with [Michael Griffiths](mailto:m.griffiths@method.me) and [Michael Melo](mailto:michael@method.me) about it that is under final code review.
2. We intend to develop a PowerShell script, scheduled to run daily, to restart the MethodTCPIP service every morning.
3. Intend to do a heartbeat for the MethodTCPIP service.

‌

---

‌

‌

Thursday Oct 26th, 2023

‌

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1698327678362799) channel about Method:Sidebar - Method:Sidebar for Gmail not working.

**Duration:** 10h (Start: 12:00 AM to 10:00 AM)

**Summary:** Some users are experiencing issues using the Method Gmail Sidebar. Retrieving data/etc.

**Impact:** All users using Gmail Sidebar.

**Root Cause:** App pool got corrupted.  Recycling on both MSN01/02 resolved issues.

‌

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1698327678362799) channel about customers getting notified of app routine failures for a different account ([ticket](https://method.atlassian.net/browse/PL-43767)).

**Duration:** 31h (Start: Thursday Oct 26th 9:58 AM to Friday Oct 27th 5:20 PM)

**Summary:** An email was sent specifically to 20 admins in container1 containing sensitive user information. This was a known issue and has happened before.

**Impact:** Randomly impacted accounts. Specifically in this instance container1 was impacted.

**Root Cause:** There is a somewhat unknown issue with the server which needs to be restarted to fix (requires downtime). 

‌

‌

---

‌

‌

---

‌

‌

### **Wednesday Oct 25th, 2023**

‌

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1698248931247129) channel about Report server and service with error “E008 - Request failed with Status Code InternalServerError”

**Duration:** 1 hour 14 minutes (Start: 10:37 AM to 11:51 AM)

**Summary:** 

User is trying to print Sales Orders and they receive an error on the Generate Report action. The error is: ”E008 - Request failed with Status Code InternalServerError and content {"Message":"ERROR: There was an unspecified error loading the report. Please check your Generate Report action to ensure all fields are setup properly, and that the report loads correctly in the report designer."}

**Impact:**  

Users were not able to generate reports. List of affected users:

appstructures

arrowconservation2

hidcorind

miamihuaxingtradecorporation

completeelectricalsolutions

englandlogistics

redeagleinternational

georgiastage

chapmanco

cggschmidt2

rainguardok

oregonrestorationco

rlhindustriesinc2

sitepreps

worldsecurityandelectric

apexstone

crscorporaterelocationsystemsinc

careerproglobal

freedomrangerhatcheryinc

organizedinteriors

ctsolutions

farmxs

homesteadstructures

t1lightinginc

chimeraintegrationsllc

cmisales

crslaboratories

ginternationaltradingcorp

imperialprivacysystemsllc

maconstructiongroup

magnummarketing

patchmypc

seatify

skyproduct

tcmerrittslandsurveyors

tristatebiomedicalsolutions2

bindersincco1

brpmett02

eastwestemb2

foxmark

happydayflower

industrialhorsepowerplus

pondershollow

sierrapadre

bakerhookerandassociates

cabinetcornerllc

lenworth

pavemasterpavinginc2

refexpertsandhvacllc

solventdirect

JudicialServicesCR

bonopussales

chargesmartevllc

firestationfurniture

fujimats

holdit

lancasterandassociatesinc2

lancevalves2

lawsondrayage

mobilitycitycolumbusoh2

ozopenergysystemsinc

prestigeislandexports

prioritek

procurementequipment

wildcatstriping

cornerstonetf

deltakits1

dentmagicswltd

durabikelocker

ecowerks

flh

glacierhops

infoforyoullcdbaarisawater2

longspringtradingcorp2

maplevalley

skylinemetalroofingproductsinc

surfaceco

tcg3

CryturUSA

amesresearchinc

andys

canadakegsandpackaging3

centrallibertyproperties

completechillersolutionsinc

connectdirectinc

countryhomecreations

empireelectronicsinc

firesafetyservicesinc2

georgiastagerestore20231024

indianaautomotiveequipment

joyolightgroupinc7

kandbfloorcoveringllc

kgmenterprises

mdbiologix

monogramcabinetry

mpdmedical

namusa

nukitchens132

packagingoptionsusa

planttours

prostack

refreshdeal

shedsunlimited

solsticeag

suncoastenclosures1

suntreksolar

vcssalesanddistribution

washlincllc

BenShaffer

CunninghamPianoCo

FlowTurn

GarageLivingChicago

accurateforklift3

bham

biggameusaco2

bodegatile

botanaway

caribbeandiagnosticsltdco1

comfortzonewindowtinting

crcontracting

cryturusa

cunninghampianoco

currentinstrumentationandautomationinc

dealer121

delmarvadesigncenter

deluxesystems

dewesoft

directflooring

expressassembly1

glw2021

hushcityspco1

judicialservicescr

lesencres3

lespoochs

mfmh

mustangsouth

neworleanslouisiana

nwdisplays

ontariometalproducts3

peterlugerbrooklyn

pipespy2

rainguardokrestore20231024

reflektechnologiescorporation

screensofgeorgia

shercomindustries3

sylvacorp

symbiosisuklimited

thestoragegroup

wholelogreclaimed3

wilkindennyslimited

‌

**Root Cause Analysis:**

‌

**Action Items:**

A ticket was created for investigation and fixing the root cause.

[Error on Generate Report action on new prod-report-01 machine](https://method.atlassian.net/browse/PL-43727)

[Sales Order - "Action execution error" when print reports](https://method.atlassian.net/browse/PL-43721) (p0)

‌

---

‌

‌

---

‌

‌

Wednesday Oct 25th, 2023

**Incident/Alert:**

We have started seeing a lot of MongoDb version incompatible errors for Intercom-api in Logstash

_Server at localhost:27017 reports wire version 4, but this version of the driver requires at least 6 (MongoDB 3.6.0).|MongoDB.Driver.MongoIncompatibleDriverException: Server at localhost:27017 reports wire version 4, but this version of the driver requires at least 6 (MongoDB 3.6.0)._

**Duration: 5d** (the issue seems started on Oct 20th after release, but errors synced to Logstash on Oct 25th)

**Summary:** legacy-intercom-api has been using its own Mongo db on Utility2-Prod server where MongoDb was old and hasn't been upgraded, so upgrading nuget packages in the project has caused version conflicts

**Impact:** Users info is out of date in Intercom 

**Root Cause:** MongoDb Driver nuget updates, as well as legacy-intercom-api had been not connecting to the correct MongoDb

**Action Items:** MongoDb connectionstring has been updated, as well as we had bulk update for users after hotfix

‌

‌

---

‌

‌

---

‌

‌

‌

### **Tuesday Oct 24th, 2023**

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1698327678362799) channel about customers getting notified of app routine failures for a different account ([ticket](https://method.atlassian.net/browse/AS-11146)).

**Duration:** 3 days 7 hrs (Start: Tuesday Oct 24th 4:19 PM to Saturday Oct 28th 12:13 AM)

**Summary:** A migration ran on all accounts instead of just HWIT accounts. This led to app updates running on  \~50 accounts adding HWIT fields that were visible to users, and 2 apps visible to Method Support.

**Impact:** 50 accounts could see additional tables and fields (HW)

**Root Cause:** Attention to detail, missed issue in review, migration fragility/lack of pre-run reporting/checks and balances.

‌

‌

---

‌

‌

---

‌

‌

### **Friday Oct 20, 2023**

‌

**Incident/Alert:**

MSL-03 Out of memory caused the services to become unresponsive

‌

**Duration:** 7 mins (2:01 PM to 2:08 PM)

‌

**Summary:** 

‌

`Oct` `20` `18:03:07` `ip-172-31-94-57` `kernel:` `[6614022.605110]` `Out` `of` `memory:` `Killed` `process` `23349` `(mongorestore_or)` `total-vm:4043480kB,` `anon-rss:2673100kB,` `file-rss:0kB,` `shmem-rss:0kB,` `UID:1002` `pgtables:5484kB` `oom_score_adj:0`

MSL-03 RAM went out of memory, which caused the services on the machine to become unresponsive to centreon. Thus alerts popped up in #alert-system channel and x-matters.

‌

**Impact:** No impact, as one healthy instance (MSL-04) was present in the target group.

‌

**Root Cause Analysis:**

‌

**Action Items:** 

Restarted the machine, the services were back to normal.

‌

---

‌

‌

---

‌

‌

Monday Oct 16th, 2023

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1697482546006679) channel about Connection failure error on Sync Engine: Real-time sync between Method - QuickBooks Desktop was down.

**Duration:** 48m (Start: 9:18AM to End: 10:06 AM)

**Summary:** Connection status on Method Integration Engine was showing disconnected.  Signals Real Time Sync wasn’t working from Method to QBDT file.

**Impact:** All QBDT users.

**Root Cause:** Service for MethodTCPIP was found to have a status of stopping.  Killed the process and restarted the service on Utility3-Prod.

**Action Items:** Ticket created to create a health check, and centreon alert.

‌

Thursday Oct 12, 2023

‌

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1697115584895089) channel about users are not able to load the dashboard.

‌

**Duration:** 8 mins

‌

**Summary:**

When the 'method-platform-ui' release failed on one of the TFS agents, it was perceived as a failure. As a result, the TFS agent was restarted. During this process, one instance had already been removed from the target group. When the release was rerun for a short period, the other healthy instance was also removed, causing an incident.

‌

**Impact:**

Some users experienced issues loading Method.

 

**Root Cause Analysis:**

We need to ensure that our PowerShell script, which deregisters the instances, checks that at least one healthy instance remains in the target group.

**Action Items:**

A ticket was created for investigation and fixing the root cause.

[\[PL-43460\] M:UI failing deployment deleted the target group on prod and brought down production server - JIRA (atlassian.net)](https://method.atlassian.net/browse/PL-43460)

The script was updated to take into account having a healthy instance before deregistering the one specified. 

‌

‌

‌

‌

---

‌

‌

---

‌

‌

### **Wednesday Oct 11, 2023**

‌

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1697032649744399) channel about users experiencing issues loading Method.

‌

**Duration:** 7 mins

‌

**Summary:**

The Appcues JS library ([https://fast.appcues.com/13047.js](https://fast.appcues.com/13047.js)) appears to have started timing out around 9:55am or took an unusually long time to download on the UI. An alert was raised in the [performance channel](https://methodme.slack.com/archives/C05NSUS15PV/p1697032931202659). Upon investigation, it was found that this particular JS file took approximately 56 seconds to load, then it resolved on its own after a few minutes.  

![](blob:https://media.staging.atl-paas.net/?type=file&localId=f0fb6222-d0b7-42c0-ae18-1355dc0fd455&id=179d359e-c668-488e-87f9-e991f6a3b96c&&collection=contentId-133496969&height=227&occurrenceKey=null&width=941&__contextId=null&__displayType=null&__external=false&__fileMimeType=null&__fileName=null&__fileSize=null&__mediaTraceId=null&url=null)
‌

**Impact:**

Some users experienced issues loading Method.

 

**Root Cause Analysis:**

We need to make all our third party resources specially those to do with analytics and user monitoring asynchronous with a timeout. Currently there are a number of these libraries are still loading synchronously and the whole platform are dependent on them. 

‌

**Action Items:**

A ticket was created for investigation and fixing the root cause.

[https://method.atlassian.net/browse/PL-43410](https://method.atlassian.net/browse/PL-43410?atlOrigin=eyJpIjoiNDA3NTE3NDkxN2VhNGYxNzliNmFkYmUyOTY5OTE0OWEiLCJwIjoiamlyYS1zbGFjay1pbnQifQ)

[\[PL-43431\] Investigate and ensure third party dependency libraries on the front end - JIRA (atlassian.net)](https://method.atlassian.net/browse/PL-43431)

Potentially we will be looking into increasing the frequency of Synthetic tests from datadog. 

‌

We need to categorize these into two separate buckets

* those that Method are dependent on them

    * we can cache them in our own CDN 
    
* those that are just for monitoring or analytics 

    * we can make these async with timeout
    

‌

‌

---

‌

‌

---

‌

### **Sunday Sep 25, 2023**

‌

**Incident/Alert:**

A report came in on the [#swat](https://methodme.slack.com/archives/C01L5K42GQ6/p1695570771929889) channel about users sporadically encountering errors on the UI when trying to save on different screens.

‌

**Duration:** 72 mins

‌

**Summary:**

After checking the Logstash logs, it was discovered that one of the four runtime-core-api instances (rt-prod-4) couldn't establish any new connections to Elasticache Redis. Restarting the service addressed this issue.   
It seems that the Elasticache maintenance and backups are scheduled for Sundays between 11:30 and 12:30, and the failure began occurring during this period.

‌

![](blob:https://media.staging.atl-paas.net/?type=file&localId=3e1aa029-bcb6-4234-a24d-e637c7ae7540&id=dc22a5f2-a688-4c23-8548-b7f2d33fadee&&collection=contentId-133496969&height=313&occurrenceKey=null&width=1050&__contextId=null&__displayType=null&__external=false&__fileMimeType=null&__fileName=null&__fileSize=null&__mediaTraceId=null&url=null)
‌

**Impact:**

Some users experienced issues saving screens. However, attempting again on the same screen resolved the problem.

‌

**Root Cause Analysis:**

During the weekly/monthly AWS maintenance, some services couldn't establish a connection to the Redis cluster. It seems our code lacked a reconnect logic, and since the Redis connection was established during application startup, it continuously tried to reconnect while in that broken state.

‌

**Resolution and Mitigation:**

RT-4 was restarted and since a new Redis connection was created, the problem was resolved. 

‌

**Action Items:**

A ticket was created for investigation 

[\[PL-43102\] Investigate Redis Failures - JIRA (atlassian.net)](https://method.atlassian.net/browse/PL-43102) 

‌

The following are required to prevent Redis being a single point of failure:

1. Bump up the StackExchange.Redis NuGet to the latest version

    1. If you are using Microsoft.Extensions.Caching.Redis, be aware that this package was deprecated and you have to use Microsoft.Extensions.Caching.StackExchangeRedis going forward.
    2. If you can’t use Microsoft.Extensions.Caching.StackExchangeRedis  due to framework limitation or any other reason, make sure to install the latest version of StackExchange.Redis this should override the underlying version that Microsoft.Extensions.Caching.StackExchangeRedis uses.
    

‌

2. You need to make sure that your Redis api within your code is fault tolerant, meaning that if there is a failure during connection or command execution it should fall back and read the data from the actual DB. If you are using Microsoft.Extensions.Caching.StackExchangeRedis or the ms-core NuGet (Method.Core.Caching) you just need to upgrade it to the latest version.

‌

3. If you have your own Redis implementation in your code similar to runtime-stack, you need to make some changes to allow Redis reconnect, have a look at this ticket [\[PL-43102\] Investigate Redis Failures - JIRA (atlassian.net)](https://method.atlassian.net/browse/PL-43102) and this PR [#PL-43102 - bumped up Redis NuGet and made CacheContext fault tolerant by apakbaz · Pull Request #1411 · methodcrm/runtime-core (github.com)](https://github.com/methodcrm/runtime-core/pull/1411) specifically the CacheContext class and you can follow how we did it there. 

‌

**Supporting Information:**

Here’s some articles for you to read and refer to:

* [Best practices for connection resilience - Azure Cache for Redis | Microsoft Learn](https://learn.microsoft.com/en-us/azure/azure-cache-for-redis/cache-best-practices-connection)
* [Sudden "RedisConnectionException: No connection is active/available to service this operation" on v2.1.30 · Issue #1510 · StackExchange/StackExchange.Redis (github.com)](https://github.com/StackExchange/StackExchange.Redis/issues/1510)

‌

‌

---

‌

‌

---

‌

###             **Monday Sep 13, 2023**

‌

**Incident/Alert:**

ms-account health check failure over the night due to disk failure.

‌

**Duration:** 10 mins

‌

**Summary:**

By looking at the logs in MSL04, it looks like at around 4:24 we lost the connectivity to the Fsx share drive on Amazon

‌

Sep 14 08:24:07 ip-172-31-120-89 kernel: \[3468526.318341\] CIFS VFS: \\\\prod-fsx has not responded in 180 seconds. Reconnecting...

Sep 14 08:24:07 ip-172-31-120-89 kernel: \[3468526.337094\] CIFS VFS: \\\\prod-fsx\\share BAD_NETWORK_NAME: \\\\prod-fsx\\share

‌

Further looking at the metric on Amazon Fsx, it seems that we lost file server (managed by Amazon) at around 4am for 20 mins

It seems that our Fsx file system is a Single-AZ and based on this support article during the maintenance they can't guarantee availability

‌

**Impact:**

Nothing really, we didn't have any process needing the shared folder

What is this shared Fsx used for:

* It holds the file share witness for SQL
* It's used for offline generation
* It's used for copy db

‌

**Action Items:**

We have to change our deployment type to <MultiAz> but unfortunately our region does not support the MultiAZ file system yet.

We may need to move to it to US-WEST2 to change the deployment type and we need to recreate the whole file system I think (pending verification)

‌

‌