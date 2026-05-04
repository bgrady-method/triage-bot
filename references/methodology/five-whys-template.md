# Five-Whys protocol (blameless)

Used at Phase 5 of `stability-review-prompt.md`. Every cluster gets a five-whys trace. Each "why" cites at least one piece of evidence; the 5th "why" must surface a structural cause.

## Required shape

```
Symptom: <one-line description of the user-visible failure>

Why 1: <why did the user-visible failure happen?>
  Evidence: <log line / monitor query / Jira ticket / deploy hash / trace id>

Why 2: <why did Why 1 happen?>
  Evidence: <…>

Why 3: <why did Why 2 happen?>
  Evidence: <…>

Why 4: <why did Why 3 happen?>
  Evidence: <…>

Why 5: <why did Why 4 happen — STRUCTURAL>
  Evidence: <…>

Stop condition: <why we stopped here, e.g., "5th why is a process/architecture root">
```

## Rules

1. **Cite evidence at every step.** A claim without a citation is a guess. If you can't cite, mark the why as `(unverified — needs investigation)` and stop the chain at that depth.
2. **Blameless framing.** Replace "Engineer X didn't do Y" with "the system did not surface Y" or "the process did not require Y". The structural cause is almost never an individual.
3. **Distinguish proximate from structural.** Proximate causes are what triggered this incident. Structural causes are why this *class* of incident is possible. The 5th why must be structural.
4. **Stop at structural, not at "human error".** If you arrive at "the engineer should have done X", you have one more why to ask: "why was X required of an engineer rather than enforced by the system?"
5. **One chain per cluster.** If a cluster has two distinct symptoms, split into two clusters with two chains.
6. **Don't pad to 5.** If you reach a structural cause at why 3 or 4, stop and document. Padding creates fake depth.
7. **Don't flatten to fewer than 3.** A 2-why analysis ("user clicked button → button was buggy → fix the button") is not RCA — it's a bug fix masquerading as RCA. Force at least 3 layers.

## Examples

### Good — ends at structural

```
Symptom: Users saw stale screens for 45 minutes on 2026-04-12.

Why 1: Cache wasn't invalidated for the affected accounts.
  Evidence: kb/incident-log.jsonl line 142 (alert_hash=abc123, classification=known-issue-recurrence);
            DD log "Subscriber heartbeat last seen 14:22" (https://app.datadoghq.com/logs?query=...).

Why 2: Runtime.Core.Subscriber.Agent stopped consuming RabbitMQ events.
  Evidence: DD metric `rabbitmq.queue.messages` for `tables-fields.view.change` rose monotonically
            from 14:22 to 15:07 (https://app.datadoghq.com/dashboard/...).

Why 3: No alert fired when the agent went silent.
  Evidence: dd_search.py monitors --tag service:runtime-core-subscriber returned 0 results.

Why 4: No DD monitor exists for the agent's heartbeat or its consumer lag.
  Evidence: Confirmed by exhaustive monitor search across service:runtime-core-* tags.

Why 5: The agent has no defined SLO, so the ops contract does not require a heartbeat monitor.
  Evidence: runtime-core/CLAUDE.md performance section lists API SLOs only;
            no entries for the Subscriber agent or any background consumer.

Stop condition: Reached structural cause — missing SLO drives missing monitor drives invisible service.
```

### Bad — stops at proximate

```
Symptom: Users saw stale screens.
Why 1: Cache wasn't invalidated.
Why 2: The Subscriber agent was stopped.
Why 3: An engineer ran an "iisreset" without restarting the agent.
Stop: Tell the engineer to restart the agent.
```

This stops at the proximate cause and converts the analysis into blame. The right next why is "why didn't iisreset automatically restart the agent?" or "why was iisreset run during business hours without procedure?"

### Bad — fake depth

```
Why 1: Cache wasn't invalidated.
Why 2: Because the agent was stopped.
Why 3: Because the agent crashed.
Why 4: Because the agent had a bug.
Why 5: Because software has bugs.
```

Each step restates the prior. The chain reaches no actionable structural cause.

## Where this lives in the report

The five-whys trace appears verbatim under each cluster's "Findings" entry. It precedes the recommendation, because the recommendation must address the structural cause from why 5.
