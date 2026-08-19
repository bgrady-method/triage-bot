"""One-shot script: append all incident-log lines for the 14:08Z cycle."""
import json
from pathlib import Path

NOW = '2026-06-09T14:08:00Z'

log_path = Path('kb/incident-log.jsonl')
lines = []

def write(entry):
    lines.append(json.dumps(entry, ensure_ascii=False))

# Group A satellites first (step 2 of routine)
group_a_primary = 'd1055229a9b24ee9'
group_a_sats = ['b9b81341a1a4688e','a94255a6523e6b47','fc17383bb160ff31','4bb51130eb096303',
                '2aad7e1a47d9957f','bfac68699d0dc20f','33baaf17348fdabd','dd619338ace8d0aa',
                '66ac8283ad8223ad','3879cf993e1a92eb','dd96abb32c3792bf','b2a417774047025f',
                '33eface1b3e78f80','8890754fa25a0262','a7b8a29c13c6472d']
group_a_grouped = [group_a_primary] + group_a_sats
group_a_sat_slack_ts = ['1781011032.404599','1781011332.546049','1781011453.157269','1781011872.596749',
                       '1781012053.125029','1781012172.966249','1781012292.740379','1781012413.101339',
                       '1781012712.644079','1781013134.117379','1781013253.291569','1781013312.915259',
                       '1781013372.996479','1781013433.443119','1781013673.441729']
group_a_sat_iso = ['2026-06-09T13:17:12Z','2026-06-09T13:22:12Z','2026-06-09T13:24:13Z','2026-06-09T13:31:12Z',
                  '2026-06-09T13:34:13Z','2026-06-09T13:36:12Z','2026-06-09T13:38:12Z','2026-06-09T13:40:13Z',
                  '2026-06-09T13:45:12Z','2026-06-09T13:52:14Z','2026-06-09T13:54:13Z','2026-06-09T13:55:12Z',
                  '2026-06-09T13:56:12Z','2026-06-09T13:57:13Z','2026-06-09T14:01:13Z']

for sh, sts, siso in zip(group_a_sats, group_a_sat_slack_ts, group_a_sat_iso):
    write({
        'ts': siso, 'alert_hash': sh, 'channel': 'alert-frontend-errors',
        'classification': 'grouped', 'matched_kb': None, 'confidence': None,
        'action': f'grouped-with:{group_a_primary}', 'grouped_with': group_a_primary,
        'slack_ts': sts, 'bot_id': 'B011R3D650X',
        'duration_s': 0, 'runtime_cost_usd': 0
    })

# Group A primary
write({
    'ts': NOW, 'alert_hash': group_a_primary, 'channel': 'alert-frontend-errors',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-21-gateway-microservices-timeout',
    'confidence': 0.90,
    'action': 'suppressed-dm:known-issue-window',
    'grouped_alerts': group_a_grouped,
    'investigation_doc': f'docs/investigations/2026-06-09-{group_a_primary}.md',
    'slack_ts': '1781010973.596939', 'bot_id': 'B011R3D650X',
    'monitor_id': '77419271', 'monitor_name': 'Unusual number of XHR errors for account: {{@account_name.name}}',
    'service_affected': 'ms-gateway-api (Ocelot proxy) / microservices.method.int sync-util',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 342,
    'bug_type_guess': 'env',
    'escalation_score': 2,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-21-gateway-microservices-timeout'},
        {'signal': 'critical_path_service', 'delta': 3, 'value': 'ms-gateway-api', 'source': 'monitor 77419271 + DD log path attribution'},
        {'signal': 'group_size_5_9_or_10plus', 'delta': 4, 'value': 16},
        {'signal': 'cross_channel', 'delta': 2, 'value': 2, 'notes': 'co-fire with alert-system Groups E/F (5 alerts B011R3D650X cross-channel)'},
        {'signal': 'active_users_affected', 'delta': 1, 'value': 20, 'source': 'dd-logs-distinct-account-cap30', 'user_count_source': 'cluster_lower_bound', 'accounts_resolved': 0},
        {'signal': 'monitor_history', 'delta': 1, 'value': 'monitor 77419271 high dm_rate historically (>=0.8)'},
        {'signal': 'metric_breach', 'delta': 1, 'value': {'observed_p95_s': 7.05, 'threshold_s': 3.0, 'ratio': 1.35, 'bracket': '1.0-2.0'}},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403 chronic'},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-21 DM 2026-06-09T12:13:08Z ~1h55m ago'},
        {'signal': 'recency_decay', 'delta': -2, 'value': '3rd ki-21 cycle today (12:08/13:08/14:08)'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies on frontend channel; eyes reactions on runtime channel only'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'no accounts resolved'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'Canonical ki-21 chronic gateway-fan-out. 16-alert cluster in 45 min on alert-frontend-errors, 5 cross-channel B011R3D650X fires on alert-system (Groups E/F). DD logs 20 distinct accounts sample-cap-saturated. Co-fires with ki-24 runtime spike (Groups B/C/D). NEW corroboration: Redis errors fired monitor 227940275 13:37:36Z (first joint observation in ki-21 cycle history). KB occ 341->342. DM suppressed within 24h window.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group B satellites
group_b_primary = 'f09b91fd6248145f'
group_b_sats = ['64bb8dee002cd4ac','c7394007c4095562','8a8ba171d3fcaf1a','6c02372ee899d081',
                '227dafb59176e519','76e45afebaaf58c2','e566d3ec657eeef3','d67fe0e10073c454',
                '97ec4f7ca35bd826','04af1d991676948d','c0393155bed9be83','4b926fe6138f5a86','f11f1fc4228e3670']
group_b_grouped = [group_b_primary] + group_b_sats
group_b_sat_slack_ts = ['1781011313.345259','1781011327.053529','1781012130.632449','1781012131.071059',
                       '1781012220.370679','1781012277.045789','1781012298.165209','1781012302.678789',
                       '1781012310.386879','1781012332.406049','1781012371.069809','1781012420.897519','1781012464.404449']
group_b_sat_iso = ['2026-06-09T13:21:53Z','2026-06-09T13:22:07Z','2026-06-09T13:35:30Z','2026-06-09T13:35:31Z',
                  '2026-06-09T13:37:00Z','2026-06-09T13:37:57Z','2026-06-09T13:38:18Z','2026-06-09T13:38:22Z',
                  '2026-06-09T13:38:30Z','2026-06-09T13:38:52Z','2026-06-09T13:39:31Z','2026-06-09T13:40:20Z','2026-06-09T13:41:04Z']

for sh, sts, siso in zip(group_b_sats, group_b_sat_slack_ts, group_b_sat_iso):
    entry = {
        'ts': siso, 'alert_hash': sh, 'channel': 'alert-runtime-monitoring',
        'classification': 'grouped', 'matched_kb': None, 'confidence': None,
        'action': f'grouped-with:{group_b_primary}', 'grouped_with': group_b_primary,
        'slack_ts': sts, 'bot_id': 'B063S8NBW0M',
        'duration_s': 0, 'runtime_cost_usd': 0
    }
    if siso >= '2026-06-09T13:37:00Z':
        entry['reactions'] = {'eyes': 1}
    write(entry)

write({
    'ts': NOW, 'alert_hash': group_b_primary, 'channel': 'alert-runtime-monitoring',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-24-runtime-core-rtc-p95-recurring',
    'confidence': 0.85,
    'action': 'suppressed-dm:known-issue-window',
    'grouped_alerts': group_b_grouped,
    'investigation_doc': f'docs/investigations/2026-06-09-{group_b_primary}.md',
    'slack_ts': '1781010606.825079', 'bot_id': 'B063S8NBW0M',
    'monitor_id': '17872725',
    'monitor_name': 'Service runtime-core-api has a high p90 latency on env:prod (B063S8NBW0M lineage)',
    'service_affected': 'runtime-core-api',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 106,
    'bug_type_guess': 'env',
    'escalation_score': 3,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-24-runtime-core-rtc-p95-recurring'},
        {'signal': 'critical_path_service', 'delta': 3, 'value': 'runtime-core-api'},
        {'signal': 'group_size_5_9_or_10plus', 'delta': 4, 'value': 14},
        {'signal': 'cross_channel', 'delta': 2, 'value': 3, 'notes': 'cross-channel co-fire with ki-21 storm Groups A/E/F'},
        {'signal': 'metric_breach', 'delta': 1, 'value': {'observed_p95_s': 7.05, 'threshold_s': 3.0, 'ratio': 1.35, 'bracket': '1.0-2.0', 'source': 'Screen Load p95 sustained tail; primary 132s in prior cycle'}},
        {'signal': 'active_users_affected', 'delta': 0, 'value': 0, 'source': 'account_impact.py-skipped', 'user_count_source': 'named_only'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403; runtime-core last deploy 19+ days'},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-24 DM 2026-06-08T18:18:17Z 19h50m ago'},
        {'signal': 'recency_decay', 'delta': -2, 'value': '3rd B063S8NBW0M fire today'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': '9 eyes reactions on satellites 13:37-13:41Z but NO thread replies'},
        {'signal': 'monitor_history', 'delta': 0, 'value': '17872725 limited explicit history'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'Continuation/aftershock of prior cycle G3 anomalous-severity event (132s peak 13:07:40Z). 14-alert sustained tail with 9 eyes reactions 13:37-13:41Z (operator engagement signal, but no thread replies = rubric not triggered). NEW Redis errors fired 13:37:36Z within span (first observed Redis-error corroboration in ki-24 history). DD synthetics cluster fired 13:46-13:51Z. KB occ 105->106. STABILITY-REVIEW FLAG: ki-24 anomalous-severity case continues.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group C primary
group_c_primary = '620afd596350e898'
write({
    'ts': NOW, 'alert_hash': group_c_primary, 'channel': 'alert-system',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-24-runtime-core-rtc-p95-recurring',
    'confidence': 0.85,
    'action': 'suppressed-dm:known-issue-window',
    'grouped_alerts': [group_c_primary],
    'investigation_doc': f'docs/investigations/2026-06-09-{group_c_primary}.md',
    'slack_ts': '1781010606.592519', 'bot_id': 'B05PN7JG87L',
    'monitor_id': '17872725',
    'monitor_name': 'Service runtime-core-api has a high p90 latency on env:prod (B05PN7JG87L lineage)',
    'service_affected': 'runtime-core-api',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 107,
    'bug_type_guess': 'env',
    'escalation_score': 0,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-24-runtime-core-rtc-p95-recurring'},
        {'signal': 'critical_path_service', 'delta': 3, 'value': 'runtime-core-api'},
        {'signal': 'group_size_1', 'delta': 0, 'value': 1},
        {'signal': 'cross_channel', 'delta': 2, 'value': 2, 'notes': 'same-second cross-channel co-fire with Group B 13:10:06Z'},
        {'signal': 'metric_breach', 'delta': 1, 'value': {'observed_p95_s': 5.95, 'threshold_s': 3.0, 'ratio': 0.98, 'bracket': '0.5-1.0'}},
        {'signal': 'active_users_affected', 'delta': 0, 'value': 0},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-24 DM 2026-06-08T18:18:17Z'},
        {'signal': 'recency_decay', 'delta': -1, 'value': '3rd B05PN7JG87L fire today'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies on alert-system'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'},
        {'signal': 'monitor_history', 'delta': 0, 'value': 'limited B05PN7JG87L history'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'ki-24 cross-channel co-fire — same-second as Group B 13:10:06Z. B05PN7JG87L alert-system sibling of B063S8NBW0M. KB occ 106->107 per separate-group bump.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group D primary
group_d_primary = '9519b28130444baf'
write({
    'ts': NOW, 'alert_hash': group_d_primary, 'channel': 'alert-system',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-24-runtime-core-rtc-p95-recurring',
    'confidence': 0.80,
    'action': 'suppressed-dm:known-issue-window',
    'grouped_alerts': [group_d_primary],
    'investigation_doc': f'docs/investigations/2026-06-09-{group_d_primary}.md',
    'slack_ts': '1781013696.454539', 'bot_id': 'B05PN7JG87L',
    'monitor_id': '17872725',
    'monitor_name': 'Service runtime-core-api high p90 latency (lineage; 4m36s forwarder lag from Screen Load 13:57Z peak)',
    'service_affected': 'runtime-core-api',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 108,
    'bug_type_guess': 'env',
    'escalation_score': 0,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-24-runtime-core-rtc-p95-recurring'},
        {'signal': 'critical_path_service', 'delta': 3, 'value': 'runtime-core-api'},
        {'signal': 'group_size_1', 'delta': 0, 'value': 1},
        {'signal': 'cross_channel', 'delta': 2, 'value': 3, 'notes': 'micro-cascade A/D/G within 79 seconds'},
        {'signal': 'metric_breach', 'delta': 1, 'value': {'observed_p95_s': 6.33, 'threshold_s': 3.0, 'ratio': 1.11, 'bracket': '1.0-2.0'}},
        {'signal': 'active_users_affected', 'delta': 0, 'value': 0},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-24 DM 2026-06-08T18:18:17Z'},
        {'signal': 'recency_decay', 'delta': -2, 'value': '4th B05PN7JG87L fire today'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'},
        {'signal': 'monitor_history', 'delta': 0, 'value': 'limited B05PN7JG87L history'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'ki-24 4m36s forwarder lag from Screen Load 13:57Z 6.33s peak. Late-cycle micro-cascade A->D->G in <2 min. KB occ 107->108.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group E satellites + primary
group_e_primary = 'a7f7875eb58867e6'
group_e_sats = ['5086bf3969dbcc10','558ae12029488958','1d10eafe8377a7b5']
group_e_grouped = [group_e_primary] + group_e_sats
group_e_sat_slack_ts = ['1781011255.082909','1781011484.055789','1781012263.936709']
group_e_sat_iso = ['2026-06-09T13:20:55Z','2026-06-09T13:24:44Z','2026-06-09T13:37:43Z']

for sh, sts, siso in zip(group_e_sats, group_e_sat_slack_ts, group_e_sat_iso):
    write({
        'ts': siso, 'alert_hash': sh, 'channel': 'alert-system',
        'classification': 'grouped', 'matched_kb': None, 'confidence': None,
        'action': f'grouped-with:{group_e_primary}', 'grouped_with': group_e_primary,
        'slack_ts': sts, 'bot_id': 'B011R3D650X',
        'duration_s': 0, 'runtime_cost_usd': 0
    })

write({
    'ts': NOW, 'alert_hash': group_e_primary, 'channel': 'alert-system',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-21-gateway-microservices-timeout',
    'confidence': 0.85,
    'action': 'suppressed-dm:known-issue-window',
    'grouped_alerts': group_e_grouped,
    'investigation_doc': f'docs/investigations/2026-06-09-{group_e_primary}.md',
    'slack_ts': '1781010652.937469', 'bot_id': 'B011R3D650X',
    'monitor_id': '77419271',
    'monitor_name': 'Unusual number of XHR errors (cross-channel to alert-system)',
    'service_affected': 'ms-gateway-api',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 343,
    'bug_type_guess': 'env',
    'escalation_score': 1,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-21-gateway-microservices-timeout'},
        {'signal': 'critical_path_service', 'delta': 3, 'value': 'ms-gateway-api'},
        {'signal': 'group_size_3_4', 'delta': 2, 'value': 4},
        {'signal': 'cross_channel', 'delta': 2, 'value': 2, 'notes': 'co-fire with Group A alert-frontend-errors'},
        {'signal': 'metric_breach', 'delta': 1, 'value': {'observed_p95_s': 7.05, 'threshold_s': 3.0, 'ratio': 1.35, 'bracket': '1.0-2.0'}},
        {'signal': 'active_users_affected', 'delta': 0, 'value': 0},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-21 DM 12:13:08Z'},
        {'signal': 'recency_decay', 'delta': -2, 'value': '3rd ki-21 cycle today'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'},
        {'signal': 'monitor_history', 'delta': 0, 'value': 'consistent ki-21'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'Cross-channel duplicate of Group A. 4-alert cluster 13:10:52-13:37:43Z. KB occ 342->343 per separate-group bump.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group F
group_f_primary = 'cb443bba63e9d59f'
write({
    'ts': NOW, 'alert_hash': group_f_primary, 'channel': 'alert-system',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-21-gateway-microservices-timeout',
    'confidence': 0.85,
    'action': 'suppressed-dm:known-issue-window',
    'grouped_alerts': [group_f_primary],
    'investigation_doc': f'docs/investigations/2026-06-09-{group_f_primary}.md',
    'slack_ts': '1781014115.184569', 'bot_id': 'B011R3D650X',
    'monitor_id': '77419271',
    'monitor_name': 'Unusual number of XHR errors for account',
    'service_affected': 'ms-gateway-api',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 344,
    'bug_type_guess': 'env',
    'escalation_score': -1,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-21-gateway-microservices-timeout'},
        {'signal': 'critical_path_service', 'delta': 3, 'value': 'ms-gateway-api'},
        {'signal': 'group_size_1', 'delta': 0, 'value': 1},
        {'signal': 'cross_channel', 'delta': 0, 'value': 1, 'notes': 'late-cycle tail; rollover into next hour'},
        {'signal': 'metric_breach', 'delta': 0, 'value': 'n/a'},
        {'signal': 'active_users_affected', 'delta': 0, 'value': 0},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-21 DM 12:13:08Z'},
        {'signal': 'recency_decay', 'delta': -2, 'value': '4th ki-21 group in cycle (A/E/F/G)'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'},
        {'signal': 'monitor_history', 'delta': 0, 'value': 'consistent'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'Singleton tail of ki-21 fan-out rolling into next hour. KB occ 343->344.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group G
group_g_primary = '250759d6bc1d9003'
write({
    'ts': NOW, 'alert_hash': group_g_primary, 'channel': 'alert-system',
    'classification': 'known-issue-recurrence',
    'matched_kb': 'ki-2026-05-21-gateway-microservices-timeout',
    'confidence': 0.55,
    'action': 'suppressed-dm:lineage-ambiguous-no-bump',
    'grouped_alerts': [group_g_primary],
    'investigation_doc': f'docs/investigations/2026-06-09-{group_g_primary}.md',
    'slack_ts': '1781013752.685029', 'bot_id': 'B03GBAMHUTB',
    'monitor_id': None,
    'monitor_name': 'Centreon Flow Designer Connector — external bridge',
    'service_affected': 'unknown (external Centreon; cascade downstream of ki-21/ki-24)',
    'suppressed_dm': True, 'gate_reason': 'known-issue-window',
    'kb_occurrences_after': 344,
    'kb_bump_skipped': True,
    'kb_bump_skip_reason': 'lineage-ambiguous-default-ki21-already-bumped-3x-this-cycle (A/E/F)',
    'bug_type_guess': 'env',
    'escalation_score': -3,
    'score_breakdown': [
        {'signal': 'matched_kb_inhibition', 'delta': -3, 'value': 'ki-2026-05-21-gateway-microservices-timeout (defaulted by historical precedent)'},
        {'signal': 'critical_path_service', 'delta': 0, 'value': 'unknown — external Centreon'},
        {'signal': 'group_size_1', 'delta': 0, 'value': 1},
        {'signal': 'cross_channel', 'delta': 2, 'value': 3, 'notes': 'micro-cascade A/D/G within 79 seconds'},
        {'signal': 'metric_breach', 'delta': 0, 'value': 'n/a'},
        {'signal': 'active_users_affected', 'delta': 0, 'value': 0},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'ki-21 DM 12:13:08Z'},
        {'signal': 'recency_decay', 'delta': 0, 'value': '1st Centreon fire today'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': 'gh-api 403'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'},
        {'signal': 'monitor_history', 'delta': 0, 'value': 'rare'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False}
    ],
    'hypothesis': 'External Centreon Flow Designer cascade downstream of ki-21/ki-24 storm. 30s after Group D, 79s after Group A. Per G5 prior cycle precedent, defaulted ki-21 attribution, KB NOT re-bumped.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Group H — SWAT
group_h_primary = '9b6cb6573ca3c433'
write({
    'ts': NOW, 'alert_hash': group_h_primary, 'channel': 'swat',
    'classification': 'needs-human',
    'matched_kb': None,
    'confidence': 0.95,
    'action': 'dm-self',
    'grouped_alerts': [group_h_primary],
    'investigation_doc': f'docs/investigations/2026-06-09-{group_h_primary}.md',
    'slack_ts': '1781010888.711779', 'bot_id': 'B01LLRX9MSR',
    'monitor_id': None,
    'monitor_name': 'status.method.me incident 52aaf8b1 (Avast/Norton miurl.cc false-positive recurrence)',
    'service_affected': 'legacy-miurl-api / miurl.cc redirector (3rd-party AV classifier collateral)',
    'suppressed_dm': False, 'gate_reason': 'swat-bypass',
    'kb_occurrences_after': None,
    'bug_type_guess': 'env',
    'escalation_score': None,
    'score_breakdown': [
        {'signal': 'swat_bypass', 'delta': 'bypass', 'value': 'channel_name==swat'},
        {'signal': 'novel_no_kb_no_prior_hash_7d', 'delta': 0, 'value': False, 'notes': 'hash novel but same root incident d7fdcc416b5175d1 / 343f7603760b886c within 7d'},
        {'signal': 'group_size_1', 'delta': 0, 'value': 1},
        {'signal': 'critical_path_service', 'delta': 0, 'value': 'miurl.cc not in critical_path'},
        {'signal': 'active_users_affected', 'delta': 0, 'value': None, 'source': 'prior thread John Miranda 19:14Z scope "all portal users with AV installed"', 'user_count_source': 'cluster_lower_bound'},
        {'signal': 'cross_channel', 'delta': 0, 'value': 1},
        {'signal': 'monitor_history', 'delta': 0, 'value': 'B01LLRX9MSR no DD monitor'},
        {'signal': 'recency_decay', 'delta': 0, 'value': 'n/a'},
        {'signal': 'deploy_correlation_2h', 'delta': 0, 'value': '3rd-party AV event'},
        {'signal': 'operator_engagement', 'delta': 0, 'value': 'no thread replies yet'},
        {'signal': 'metric_breach', 'delta': 0, 'value': 'n/a'},
        {'signal': 'matched_kb_inhibition', 'delta': 0, 'value': None},
        {'signal': 'recent_dm_matched_kb_24h', 'delta': -2, 'value': 'prior d7fdcc416b5175d1 + 343f7603760b886c DMs 17-18h ago covering same root incident'},
        {'signal': 'account_tier', 'delta': 0, 'value': 'n/a'}
    ],
    'hypothesis': 'Recurrence of PL-63508 (Avast/Norton miurl.cc false-positive). 3rd public-facing surface in 18h. Vendor false-positive submissions made 2026-06-08 morning, 48h vendor review ETA pending. Status incident 52aaf8b1 likely opened to consolidate continuing customer reports. No Method-internal failure.',
    'duration_s': 0, 'runtime_cost_usd': 0
})

# Append
with open(log_path, 'a', encoding='utf-8') as f:
    for ln in lines:
        f.write(ln + '\n')

print(f'Appended {len(lines)} lines to {log_path}')
import sys
total = sum(1 for _ in open(log_path, encoding='utf-8'))
print(f'New log total lines: {total}')
