"""降雪提醒的离线测试（mock 掉 Supabase / 推送）。
运行：PYTHONPATH=lambda_package python3 tests/test_snow_checker.py"""
import os, sys, json
from datetime import date
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(SUPABASE_URL='https://sb.test', SUPABASE_SERVICE_KEY='k')
import check_snow_and_notify as sc

CANDIDATES = [
    {'resort_id': 1, 'resort_name': 'Whistler', 'user_ids': ['u1', 'u2'], 'subscribers': 2,
     'snow_date': '2026-11-13', 'snowfall_cm': 12.3, 'condition_status': 'open', 'lifts_open': 5,
     'condition_at': '2026-11-11T08:00:00', 'is_open': True, 'forecast_at': '2026-11-11T07:00:00',
     'action': 'send', 'skip_reason': None},
    {'resort_id': 2, 'resort_name': 'Kirkwood', 'user_ids': ['u3'], 'subscribers': 1,
     'snow_date': '2026-11-13', 'snowfall_cm': 22.3, 'condition_status': 'closed', 'lifts_open': 0,
     'condition_at': '2026-11-11T08:00:00', 'is_open': False, 'forecast_at': '2026-11-11T07:00:00',
     'action': 'skip', 'skip_reason': '雪场未开放（状态：closed）'},
]


def run(event, enabled, log_ret=('u2',), enq_ret=None):
    log = mock.Mock(return_value=list(log_ret))
    enq = mock.Mock(return_value=enq_ret or {'queued': list(log_ret), 'failed': []})
    direct = mock.Mock()
    with mock.patch.object(sc, '_get_candidates', return_value=CANDIDATES), \
         mock.patch.object(sc, '_is_snow_push_enabled', return_value=enabled), \
         mock.patch.object(sc, '_log_notifications', log), \
         mock.patch.object(sc, 'enqueue_snow_alert', enq), \
         mock.patch.object(sc, 'send_snow_alert_notification', direct):
        out = sc.lambda_handler(event, None)
    return json.loads(out['body']), log, enq, direct


# 试运行：开关关着也计算；未开放的雪场在 skipped 里并给出原因；不写日志、不发送
body, log, enq, direct = run({'dry_run': True}, enabled=False)
assert body['push_enabled'] is False
assert [a['resort'] for a in body['alerts']] == ['Whistler']
assert body['skipped'][0]['resort'] == 'Kirkwood' and '未开放' in body['skipped'][0]['skip_reason']
assert not log.called and not enq.called and not direct.called

# 正常运行 + 开关关闭：直接跳过，连候选都不查
body, log, enq, direct = run({}, enabled=False)
assert 'disabled' in body['message'] and not log.called and not enq.called

# 正常运行 + 开关打开：只处理 send 的雪场；先写日志，只给新写入的用户入队，带上原因
body, log, enq, direct = run({}, enabled=True)
assert log.call_count == 1 and log.call_args.kwargs['resort_id'] == 1
assert enq.call_args.args[0] == ['u2']
assert enq.call_args.kwargs['resort_id'] == 1 and '降雪提醒：Whistler' in enq.call_args.kwargs['reason']
assert enq.call_args.args[2] == date(2026, 11, 13)
assert not direct.called

# 入队失败 → 退回直接发送
body, log, enq, direct = run({}, enabled=True, enq_ret={'queued': [], 'failed': ['u2']})
assert direct.called and direct.call_args.args[0] == ['u2']

# 今天都提醒过 → 不发送
body, log, enq, direct = run({}, enabled=True, log_ret=())
assert not enq.called and not direct.called

# 读取开关失败 → 按关闭处理
with mock.patch.object(sc.requests, 'get', side_effect=RuntimeError('boom')):
    assert sc._is_snow_push_enabled() is False
print('ALL OK')

# ---- _log_notifications：去重 + ignore-duplicates + 返回新写入的用户 ----
posted = {}
class PR:
    def json(s): return [{'user_id': 'u1'}]
    def raise_for_status(s): pass
def fake_post(url, headers, params, json, timeout):
    posted.update(headers=headers, params=params, json=json); return PR()
with mock.patch.object(sc.requests, 'post', fake_post):
    new = sc._log_notifications(['u1', 'u1', 'u2'], 1, '2026-11-11', '2026-11-12', 12, None, 't', 'b')
assert new == ['u1']
assert [r['user_id'] for r in posted['json']] == ['u1', 'u2']
assert 'ignore-duplicates' in posted['headers']['Prefer'] and posted['params']['on_conflict'] == 'user_id,resort_id,notification_date'
print('LOGS OK')
