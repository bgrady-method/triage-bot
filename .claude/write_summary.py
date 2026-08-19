import json

summary = {
    'ts': '2026-06-09T14:08:30Z',
    'alert_hash': None,
    'channel': None,
    'classification': 'poll-cycle',
    'matched_kb': None,
    'confidence': None,
    'action': 'summary',
    'details': {
        'polled': 42,
        'groups': 8,
        'new': 8,
        'deduped': 3,
        'satellites_added': 31,
        'failed': 0,
        'dms_sent': 1,
        'actionable_appended': 7,
        'gate_reasons': {'known-issue-window': 6, 'lineage-ambiguous-no-bump': 1, 'swat-bypass': 1},
        'kb_bumped': ['ki-2026-05-21-gateway-microservices-timeout', 'ki-2026-05-24-runtime-core-rtc-p95-recurring'],
        'poll_window_minutes': 65,
        'notes': "42 messages polled across 4 channels (16 alert-frontend-errors, 15 alert-runtime-monitoring, 10 alert-system, 1 swat). 3 deduped (13:07:26 B05PN7JG87L 883e117a0d45f885, 13:07:26 B063S8NBW0M 27e9b37ff9a917df, 13:07:55 B03GBAMHUTB 7714b5b97851a357 all primaries from prior 13:08Z cycle). 8 new groups: G1=A alert-frontend B011R3D650X 16 alerts 13:16-14:01Z ki-21 SUPPRESS (occ 341 to 342); G2=B alert-runtime B063S8NBW0M 14 alerts 13:10-13:41Z ki-24 SUPPRESS (occ 105 to 106) WITH 9 EYES REACTIONS 13:37-13:41Z = operator-visible engagement; G3=C alert-system B05PN7JG87L 13:10:06Z singleton ki-24 SUPPRESS same-second cross-channel with G2 (occ 106 to 107); G4=D alert-system B05PN7JG87L 14:01:36Z singleton ki-24 SUPPRESS 4m36s forwarder-lag from Screen Load 13:57Z 6.33s peak (occ 107 to 108); G5=E alert-system B011R3D650X 4 alerts 13:10:52-13:37:43Z ki-21 SUPPRESS cross-channel duplicate of G1 (occ 342 to 343); G6=F alert-system B011R3D650X 14:08:35Z singleton ki-21 SUPPRESS rollover-into-next-hour (occ 343 to 344); G7=G alert-system B03GBAMHUTB 14:02:32Z Flow Designer Centreon SUPPRESS-LINEAGE-AMBIGUOUS no KB re-bump (defaulted ki-21 already 344); G8=H swat B01LLRX9MSR 13:14:48Z DM-SENT swat-bypass (recurrence of PL-63508 Avast/Norton miurl.cc false-positive, 3rd public-facing surface in 18h, vendor 48h review at ~24-30h elapsed). HEADLINE FINDINGS: (1) 35-new-alert storm in 1h = densest cycle of week, ki-21+ki-24 joint co-fire pattern continues; (2) 9 eyes reactions on B063S8NBW0M 13:37-13:41Z = operator-visible engagement during a suppression decision; rubric does not apply -3 inhibition (thread-replies-only) but recorded for stability-review on whether reactions should gate; (3) NEW Redis-error corroboration (monitor 227940275 fired 13:37:36Z, 19 errors total in window) = first observed joint Redis-error signal in ki-24 history, breaks KB title 'latency-only no errors'; (4) DD synthetics cluster fired 13:46-13:51Z (3 fires in 5 min) catching residual elevated p95 = external corroboration of degradation persistence; (5) ki-24 ANOMALOUS-SEVERITY case continues into 2nd cycle (prior 13:08Z 132s/147s peak, this 13:10-13:41Z sustained 5-7s tail); (6) micro-cascade A->D->G in 79 seconds at 14:01-14:02Z = 2nd cleanest fan-out today. today_dm_count toward cap: 1/5 (swat-bypass does not count). Tools: gh-ok (api 403/404 chronic cycle 36) / dd-monitors-ok / dd-metric-ok (Screen+Action+Redis) / dd-logs-ok / slack-ok / match_kb-bot-id-lineage-only / sql+mongo-skipped / account_impact.py-skipped (all groups block-only body); ES-skipped this cycle (per ki-21 playbook prior cycle ES Ocelot.Responder 0 results). Standing asks: #1 gh-api 403/404 chronic; #7 dd_search.py APM trace search blocker for ki-24 root cause attribution; new standing ask #8 = characterize reaction-vs-thread-reply operator-engagement signal: should eyes-reaction-streak gate suppression?"
    },
    'duration_s': 0,
    'runtime_cost_usd': 0
}
with open('kb/incident-log.jsonl', 'a', encoding='utf-8') as f:
    f.write(json.dumps(summary, ensure_ascii=False) + '\n')
print('Cycle summary written')
