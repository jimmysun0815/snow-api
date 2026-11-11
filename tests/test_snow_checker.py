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
    log, send = mock.Mock(), mock.Mock(return_value={'success_count': 2})
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
assert send.call_args.kwargs['snow_date'] == tomorrow
print('ALL OK')
