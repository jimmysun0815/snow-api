"""推送服务 / 推送 Lambda 的离线单元测试（mock 掉 Supabase REST 和 FCM）。"""
import sys, os, json, types
from unittest import mock
from datetime import date
# 运行：python3 tests/test_push_service.py   （需要已安装 firebase-admin / requests，
#        或 PYTHONPATH=lambda_package python3 tests/test_push_service.py）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.update(SUPABASE_URL='https://sb.test', SUPABASE_SERVICE_KEY='k')
import firebase_admin
from firebase_admin import messaging, exceptions as fbx
with mock.patch.object(firebase_admin, 'get_app', return_value=object()):
    import push_service as ps
    import sqs_notification_processor as sp

# ---- render ----
d={'type':'tennis_activity_nearby','template_key':'notifTennisActivityNearby','template_params':{'host_name':'Amy','court_name':'X Park','mode':'rally'}}
assert ps.render_for_locale('zh','tennis_activity_nearby',d,'附近有新场次','中文')==('附近有新场次','中文')
assert ps.render_for_locale('en','tennis_activity_nearby',d,'附近有新场次','中文')==('New match nearby','Amy is hosting a rally at X Park')
assert ps.render_for_locale('en','carpool_new_signup',{'type':'carpool_application'},'中','中')[0]=='🚗 New ride request'
assert ps.render_for_locale('en','general',{'type':'message','messageType':'text'},'张三','你好')==('张三','你好')
assert ps.render_for_locale('en','general',{'type':'message','messageType':'image'},'张三','发送了一张图片')==('张三','Sent a photo')
sd={'type':'snow_alert','template_params':{'resort_name':'Whistler','snow_date_iso':'2026-11-20','snow_amount':'12'}}
print(ps.render_for_locale('en','snow_alert',sd,'',''), ps.render_for_locale(None,'snow_alert',sd,'',''))
# ---- stringify ----
sdata=ps._stringify_data({'a':{'x':'中'},'b':None,'c':True,'d':3})
assert json.loads(sdata['a'])=={'x':'中'} and 'b' not in sdata and sdata['c']=='true' and sdata['d']=='3', sdata

# ---- send_to_users with mocked HTTP + FCM ----
calls=[]
class R:
    def __init__(s,code,body): s.status_code=code; s._b=body; s.content=json.dumps(body).encode() if body is not None else b''
    def json(s): return s._b
    def raise_for_status(s):
        if s.status_code>=400: raise Exception(f'http {s.status_code}')
def fake_get(url,headers,params,timeout):
    calls.append(('GET',url,params)); return R(200,[{'user_id':'u1','token':'tok_valid_aaaaaaaaaaaa','locale':'en'},{'user_id':'u1','token':'tok_dead_bbbbbbbbbbbbbb','locale':None},{'user_id':'u1','token':'tok_flaky_ccccccccccc','locale':'zh'}])
def fake_post(url,headers,json,timeout):
    calls.append(('POST',url,json))
    if url.endswith('push_badge_counts'): return R(200,[{'user_id':'u1','unread':4}])
    if url.endswith('push_outbox_claim'): return R(200,True)
    return R(204,None)
def fake_delete(url,headers,params,timeout):
    calls.append(('DELETE',url,params)); return R(204,None)
class Resp:
    def __init__(s,ok,exc=None): s.success=ok; s.exception=exc
sent=[]
def fake_send_each(msgs):
    sent.extend(msgs)
    out=[]
    for m in msgs:
        if 'dead' in m.token: out.append(Resp(False, messaging.UnregisteredError('gone')))
        elif 'flaky' in m.token: out.append(Resp(False, fbx.UnavailableError('later')))
        else: out.append(Resp(True))
    return types.SimpleNamespace(responses=out)
with mock.patch.object(ps.requests,'get',fake_get), mock.patch.object(ps.requests,'post',fake_post), \
     mock.patch.object(ps.requests,'delete',fake_delete), mock.patch.object(ps.messaging,'send_each',fake_send_each), \
     mock.patch.object(ps,'initialize_firebase',lambda:None):
    r=ps.send_to_users(['u1'],'附近有新场次','中文',d,'tennis_activity_nearby')
    print('result',r)
    assert r['success_count']==1 and r['invalid_count']==1 and r['retryable_count']==1
    en=[m for m in sent if 'valid' in m.token][0]
    assert en.notification.title=='New match nearby' and en.apns.payload.aps.badge==4 and en.apns.payload.aps.thread_id=='tennis_activity_nearby'
    assert json.loads(en.data['template_params'])['host_name']=='Amy'
    dels=[c for c in calls if c[0]=='DELETE']; assert 'tok_dead' in dels[0][2]['token'], dels
    # processor: outbox path → claim then mark sent
    calls.clear(); sent.clear()
    ev={'body':json.dumps({'type':'INSERT','table':'push_outbox','record':{'id':42,'user_id':'u1','notification_type':'tennis_activity_nearby','title':'t','body':'b','data':d}}),'headers':{}}
    out=sp.lambda_handler(ev,None); print('lambda',out)
    rpcs=[(c[1].rsplit('/',1)[1],c[2]) for c in calls if c[0]=='POST']
    print(rpcs)
    assert rpcs[0][0]=='push_outbox_claim' and rpcs[-1]==('push_outbox_mark',{'p_id':42,'p_status':'sent','p_error':None})
    # legacy payload (no outbox) → no claim
    calls.clear()
    ev2={'body':json.dumps({'type':'INSERT','table':'push_notification_queue','record':{'user_id':'u1','title':'t','body':'b','data':{}}}),'headers':{}}
    sp.lambda_handler(ev2,None)
    assert not any('push_outbox' in c[1] for c in calls if c[0]=='POST')
    # snow
    sent.clear()
    ps.send_snow_alert_notification(['u1'],'Whistler',date(2026,11,20),12.0,resort_id=7)
    t={m.token[:8]:(m.notification.title,m.notification.body,m.data.get('resort_id')) for m in sent}; print(t)
    assert t['tok_vali'][0]=='❄️ Snow forecast: Whistler' and t['tok_flak'][1]=='11月20日 预计降雪 12cm' and t['tok_vali'][2]=='7'
print('ALL OK')
