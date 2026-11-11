"""降雪提醒的离线测试（mock 掉 Supabase / 数据库 / 推送）。
运行：PYTHONPATH=lambda_package python3 tests/test_snow_checker.py"""
import os, sys, json, types
from datetime import date, timedelta
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if 'psycopg2' not in sys.modules:
    try:
        import psycopg2  # noqa
    except ImportError:
        pg = types.ModuleType('psycopg2'); pg.connect = None
        ext = types.ModuleType('psycopg2.extras'); ext.RealDictCursor = object
        pg.extras = ext; sys.modules['psycopg2'] = pg; sys.modules['psycopg2.extras'] = ext
os.environ.update(SUPABASE_URL='https://sb.test', SUPABASE_SERVICE_KEY='k')
import check_snow_and_notify as sc

tomorrow = date.today() + timedelta(days=1)
class Cur:
    def __enter__(s): return s
    def __exit__(s, *a): return False
    def execute(s, q, p): s.rid = p[0]
    def fetchone(s):
        return {'forecast_7d': [{'date': tomorrow.isoformat(), 'snowfall': 12 if s.rid == 1 else 1}]}
class Conn:
    def cursor(s, cursor_factory=None): return Cur()
    def close(s): pass
subs = [{'resort_id': 1, 'user_id': 'u1', 'resorts': {'name': 'Whistler'}},
        {'resort_id': 1, 'user_id': 'u2', 'resorts': {'name': 'Whistler'}},
        {'resort_id': 2, 'user_id': 'u3', 'resorts': {'name': 'Dry Hill'}}]

def run(event, enabled):
    log, send = mock.Mock(return_value=['u2']), mock.Mock(return_value={'success_count': 1})
    with mock.patch.object(sc, '_get_active_subscriptions', return_value=subs), \
         mock.patch.object(sc.psycopg2, 'connect', return_value=Conn()), \
         mock.patch.dict(os.environ, {'DATABASE_URL': 'postgres://x'}), \
         mock.patch.object(sc, '_check_already_notified', return_value=False), \
         mock.patch.object(sc, '_is_snow_push_enabled', return_value=enabled), \
         mock.patch.object(sc, '_log_notifications', log), \
         mock.patch.object(sc, 'send_snow_alert_notification', send):
        out = sc.lambda_handler(event, None)
    return json.loads(out['body']), log, send

# 试运行：开关关着也计算，不写日志、不发送
body, log, send = run({'dry_run': True}, enabled=False)
assert body['push_enabled'] is False and body['alerts'] == [
    {'resort_id': 1, 'resort': 'Whistler', 'snow_date': tomorrow.isoformat(), 'snowfall_cm': 12, 'users': 2}], body
assert not log.called and not send.called

# 正常运行 + 开关关闭：直接跳过
body, log, send = run({}, enabled=False)
assert 'disabled' in body['message'] and not send.called

# 正常运行 + 开关打开：先写日志再发送
body, log, send = run({}, enabled=True)
assert log.called and send.called and send.call_args.kwargs['resort_id'] == 1
assert send.call_args.kwargs['user_ids'] == ['u2']          # 只发给这次新写入日志的用户
assert send.call_args.kwargs['snow_date'] == tomorrow
print('ALL OK')

# ---- _get_active_subscriptions：分页 + 单独查雪场名（不依赖外键关联）----
class R:
    def __init__(s, body): s._b = body
    def json(s): return s._b
    def raise_for_status(s): pass
calls = []
def fake_get(url, headers, params, timeout):
    calls.append((url, dict(params)))
    if url.endswith('/resort_subscriptions'):
        assert 'resorts(' not in params['select']
        off = int(params['offset'])
        total = 1500
        n = max(0, min(sc.PAGE_SIZE, total - off))
        return R([{'id': off + i, 'resort_id': 1 if (off + i) % 2 else 2, 'user_id': f'u{off + i}'} for i in range(n)])
    if url.endswith('/resorts'):
        return R([{'id': 1, 'name': 'Whistler'}])   # 雪场 2 不存在 → name 为 None，走默认名
    raise AssertionError(url)
with mock.patch.object(sc.requests, 'get', fake_get):
    subs = sc._get_active_subscriptions()
assert len(subs) == 1500, len(subs)                              # 超过 1000 行没有被截断
assert sum(1 for c in calls if c[0].endswith('/resort_subscriptions')) == 2
assert {s['resorts']['name'] for s in subs if s['resorts']} == {'Whistler'}
assert any(s['resorts'] is None for s in subs)
print('SUBS OK')

# ---- _log_notifications：去重 + ignore-duplicates + 返回新写入的用户 ----
posted = {}
class PR:
    def json(s): return [{'user_id': 'u1'}]
    def raise_for_status(s): pass
def fake_post(url, headers, params, json, timeout):
    posted.update(headers=headers, params=params, json=json); return PR()
with mock.patch.object(sc.requests, 'post', fake_post):
    new = sc._log_notifications(['u1', 'u1', 'u2'], 1, '2026-11-11', '2026-11-12', 12, 71, 't', 'b')
assert new == ['u1']
assert [r['user_id'] for r in posted['json']] == ['u1', 'u2']
assert 'ignore-duplicates' in posted['headers']['Prefer'] and posted['params']['on_conflict'] == 'user_id,resort_id,notification_date'
print('LOGS OK')
