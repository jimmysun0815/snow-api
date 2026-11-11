#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firebase Push Notification Service

被两个 Lambda 共用：
  - sqs_notification_processor.py（Supabase 触发器 → push_outbox → 实时推送）
  - check_snow_and_notify.py（每小时降雪提醒）

要点：
  - 一次查出所有收件人的设备（含 locale），按设备语言渲染系统通知栏文案
  - iOS 角标 = 收件人未读通知数（push_badge_counts RPC，一次查全部收件人），不再写死 1
  - messaging.send_each 批量发送（每批 ≤ 500），按 SDK 异常类型区分
    「token 失效（删除）」和「临时错误（可重试）」
  - data 里的 dict / list 用 json.dumps 序列化（以前 str() 出来是 Python repr）
  - 日志里 token 只打前 12 位
"""

import os
import json
from datetime import date, datetime
from typing import Dict, Iterable, List, Optional, Tuple

import firebase_admin
from firebase_admin import credentials, messaging, exceptions as fb_exceptions
import requests

FCM_BATCH_SIZE = 500          # send_each 单次上限
HTTP_TIMEOUT = 10             # Supabase REST 超时（秒）


# =====================================================
# Firebase 初始化
# =====================================================

def initialize_firebase():
    """Initialize Firebase Admin SDK with service account (idempotent)."""
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    cred_path = os.environ.get('FIREBASE_SERVICE_ACCOUNT_KEY')
    if cred_path and os.path.exists(cred_path):
        cred = credentials.Certificate(cred_path)
    else:
        # GitHub Secrets / Lambda env 里的私钥是字面量 \n，需要还原成换行
        private_key = os.environ.get('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
        cred = credentials.Certificate({
            "type": "service_account",
            "project_id": os.environ.get('FIREBASE_PROJECT_ID'),
            "private_key_id": os.environ.get('FIREBASE_PRIVATE_KEY_ID'),
            "private_key": private_key,
            "client_email": os.environ.get('FIREBASE_CLIENT_EMAIL'),
            "client_id": os.environ.get('FIREBASE_CLIENT_ID'),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        })

    firebase_admin.initialize_app(cred)
    print("Firebase initialized")


# =====================================================
# Supabase REST helpers
# =====================================================

def _sb_url() -> str:
    return os.environ.get('SUPABASE_URL', '').rstrip('/')


def supabase_auth_headers(key: Optional[str]) -> Dict:
    """
    兼容两种 Supabase key：
      - 旧版 service_role JWT（eyJ…）：apikey + Authorization: Bearer
      - 新版 secret key（sb_secret_…）：只能放 apikey；放进 Authorization 会被当成
        无效 JWT 返回 401
    """
    key = key or ''
    headers = {'apikey': key}
    if not key.startswith('sb_'):
        headers['Authorization'] = f'Bearer {key}'
    return headers


def _sb_headers(extra: Optional[Dict] = None) -> Dict:
    headers = supabase_auth_headers(os.environ.get('SUPABASE_SERVICE_KEY'))
    headers['Content-Type'] = 'application/json'
    if extra:
        headers.update(extra)
    return headers


def sb_rpc(name: str, params: Dict):
    """调用 Supabase RPC，返回 JSON（void 函数返回 None）。"""
    resp = requests.post(
        f'{_sb_url()}/rest/v1/rpc/{name}',
        headers=_sb_headers(),
        json=params,
        timeout=HTTP_TIMEOUT,
    )
    resp.raise_for_status()
    if not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _in_filter(values: Iterable[str]) -> str:
    """PostgREST in.() 过滤：值用双引号包起来，避免 token 里的 : - _ 被误解析。"""
    quoted = ','.join('"' + str(v).replace('"', '') + '"' for v in values)
    return f'in.({quoted})'


def mask_token(token: str) -> str:
    return f'{token[:12]}…' if token else '<empty>'


# =====================================================
# 设备 token
# =====================================================

def get_user_devices(user_ids: List[str]) -> List[Dict]:
    """
    一次查出多个用户的设备。返回 [{'user_id','token','locale'}]。
    locale 列在迁移 155 之前不存在 —— 查询失败时自动降级为不带 locale。
    """
    user_ids = [u for u in dict.fromkeys(user_ids) if u]
    if not user_ids:
        return []

    devices: List[Dict] = []
    for i in range(0, len(user_ids), 100):          # 控制 URL 长度
        chunk = user_ids[i:i + 100]
        params = {'user_id': _in_filter(chunk), 'select': 'user_id,token,locale'}
        resp = requests.get(f'{_sb_url()}/rest/v1/device_tokens',
                            headers=_sb_headers(), params=params, timeout=HTTP_TIMEOUT)
        if resp.status_code == 400:
            params['select'] = 'user_id,token'
            resp = requests.get(f'{_sb_url()}/rest/v1/device_tokens',
                                headers=_sb_headers(), params=params, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        devices.extend(resp.json())

    # 同一 token 只发一次
    seen, unique = set(), []
    for d in devices:
        if d.get('token') and d['token'] not in seen:
            seen.add(d['token'])
            unique.append(d)
    return unique


def get_user_tokens(user_id: str) -> List[str]:
    """兼容旧调用方。"""
    return [d['token'] for d in get_user_devices([user_id])]


def delete_invalid_tokens(tokens: List[str]):
    """
    FCM 判定失效的 token：移到 device_tokens_backup_155（迁移 157 的 retire_device_tokens），
    不直接删除。RPC 不存在（157 之前）或调用失败时什么都不做 —— 失效 token 留着无害，
    下次发送 FCM 还会再报失效。
    """
    if not tokens:
        return
    try:
        moved = sb_rpc('retire_device_tokens', {'p_tokens': tokens, 'p_reason': 'invalid FCM token'})
        print(f"🗄️  {moved} 个失效 token 已移到备份表")
    except Exception as e:
        print(f"⚠️  失效 token 未移走（保留原样）: {e}")


def get_badge_counts(user_ids: List[str]) -> Dict[str, Optional[int]]:
    """收件人的未读通知数（一次 RPC）。出错时返回空 dict → 不设置角标，而不是写死 1。"""
    user_ids = list(dict.fromkeys(u for u in user_ids if u))
    if not user_ids:
        return {}
    try:
        rows = sb_rpc('push_badge_counts', {'p_user_ids': user_ids}) or []
        # 未读数为 0 时不设置角标（None = iOS 保持原样）：私信不写 notifications 行，
        # 如果发 badge=0，新私信到达时反而会把角标清掉
        return {r['user_id']: int(r['unread']) for r in rows if int(r['unread']) > 0}
    except Exception as e:
        print(f"⚠️  获取角标数失败: {e}")
        return {}


# =====================================================
# 多语言：系统通知栏文案
# =====================================================
# 触发器写入的 title / body 是中文；locale=en 的设备按模板渲染英文。
# 模板与 App 端 lib/l10n/app_en.arb 的 notif* 文案保持一致。

# data.type / notification_type → 模板 key（对齐迁移 144 的映射）
TYPE_TO_TEMPLATE = {
    'carpool_application': 'notifCarpoolApplication',
    'carpool_new_signup': 'notifCarpoolApplication',
    'carpool_approved': 'notifCarpoolApproved',
    'carpool_signup_approved': 'notifCarpoolApproved',
    'carpool_rejected': 'notifCarpoolRejected',
    'carpool_signup_rejected': 'notifCarpoolRejected',
    'accommodation_application': 'notifAccommodationApplication',
    'accommodation_new_signup': 'notifAccommodationApplication',
    'accommodation_approved': 'notifAccommodationApproved',
    'accommodation_signup_approved': 'notifAccommodationApproved',
    'accommodation_rejected': 'notifAccommodationRejected',
    'accommodation_signup_rejected': 'notifAccommodationRejected',
    'snow_alert': 'notifSnowAlert',
    'feed_reply': 'notifFeedReply',
    'feed_mention': 'notifFeedMention',
    'comment_reply': 'notifCommentReply',
    'post_hidden': 'notifPostHidden',
    'account_restricted': 'notifAccountRestricted',
    'account_unrestricted': 'notifAccountUnrestricted',
    'tennis_application': 'notifTennisApplication',
    'tennis_approved': 'notifTennisApproved',
    'tennis_rejected': 'notifTennisRejected',
    'tennis_join_request': 'notifTennisApplication',
    'tennis_join_approved': 'notifTennisApproved',
    'tennis_join_rejected': 'notifTennisRejected',
    'tennis_vote_needed': 'notifTennisVoteNeeded',
    'tennis_match_locked': 'notifTennisResultConfirmed',
    'tennis_result_pending': 'notifTennisResultPending',
    'tennis_result_confirmed': 'notifTennisResultConfirmed',
    'tennis_result_disputed': 'notifTennisResultDisputed',
    'tennis_elo_updated': 'notifTennisEloUpdated',
    'tennis_activity_nearby': 'notifTennisActivityNearby',
    'tennis_live_match_invite': 'notifTennisLiveMatchInvite',
    'tennis_activity_comment': 'notifTennisActivityComment',
    # 'message' / 'general'：标题是发送者昵称、正文是消息内容，本身与语言无关，不翻译
}

EN_TEMPLATES: Dict[str, Tuple[str, str]] = {
    'notifCarpoolApplication': ('🚗 New ride request', 'Someone wants to join your carpool'),
    'notifCarpoolApproved': ('✅ Ride request approved', 'Your ride request was approved'),
    'notifCarpoolRejected': ('❌ Ride request declined', 'Sorry, your ride request was declined'),
    'notifAccommodationApplication': ('🏠 New room request', 'Someone wants to book your room'),
    'notifAccommodationApproved': ('✅ Room request approved', 'Your room request was approved'),
    'notifAccommodationRejected': ('❌ Room request declined', 'Sorry, your room request was declined'),
    'notifSnowAlert': ('❄️ Snow alert', 'New snowfall information'),
    'notifCommentReply': ('Someone replied to your comment', 'See the new reply'),
    'notifFeedReply': ('Someone replied to your post', 'See the new reply'),
    'notifFeedMention': ('Someone mentioned you', 'See what they said'),
    'notifPostHidden': ('Your post was hidden', 'Tap to see details'),
    'notifAccountRestricted': ('Account restricted', 'Tap to see details'),
    'notifAccountUnrestricted': ('Account restriction lifted', ''),
    'notifTennisApplication': ('🎾 New match request', 'Someone wants to join your match'),
    'notifTennisApproved': ('✅ Match request approved', 'Your match request was approved'),
    'notifTennisRejected': ('❌ Match request declined', 'Sorry, your match request was declined'),
    'notifTennisResultPending': ('🎾 Score pending confirmation', 'Your opponent submitted a score — please confirm'),
    'notifTennisResultConfirmed': ('✅ Score confirmed', 'Your opponent confirmed the score; ELO updated'),
    'notifTennisResultDisputed': ('⚠️ Score disputed', 'Your opponent disputed the score you submitted'),
    'notifTennisLiveMatchInvite': ('🎾 Ranked match invite', 'Someone wants to start a ranked match'),
    'notifTennisVoteNeeded': ('🎾 Score needs a vote', 'A score is under dispute and needs your vote'),
    'notifTennisEloUpdated': ('Your ELO has updated', 'See your latest rating'),
    'notifTennisActivityNearby': ('New match nearby', 'A new match is happening near you'),
    'notifTennisActivityComment': ('New comment on your match', ''),
    'notifTennisActivityCommentRoot': ('New comment on your match', ''),
    'notifTennisActivityCommentReply': ('New reply to your comment', ''),
}

EN_TENNIS_MODES = {'rally': 'rally', 'friendly': 'friendly match', 'competitive': 'ranked match'}


def _params(data: Dict) -> Dict:
    p = data.get('template_params')
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except ValueError:
            p = None
    return p if isinstance(p, dict) else {}


def _format_date(iso: str, locale: str) -> str:
    try:
        d = datetime.fromisoformat(str(iso)[:10]).date()
    except ValueError:
        return str(iso)
    if locale == 'en':
        return d.strftime('%b %-d')
    return f'{d.month:02d}月{d.day:02d}日'


def render_for_locale(locale: Optional[str], notification_type: Optional[str],
                      data: Dict, title: str, body: str) -> Tuple[str, str]:
    """按设备语言渲染 (title, body)。非英文直接用触发器给的中文文案。"""
    lang = (locale or 'zh').lower()[:2]
    params = _params(data)

    # 降雪提醒：zh / en 都按参数渲染（日期格式随语言）
    if (data.get('type') or notification_type) == 'snow_alert' and params.get('resort_name'):
        when = _format_date(params.get('snow_date_iso', ''), lang)
        amount = params.get('snow_amount', '')
        if lang == 'en':
            return (f"❄️ Snow forecast: {params['resort_name']}", f"{amount}cm of snow expected on {when}")
        return (f"❄️ {params['resort_name']} 降雪预报", f"{when} 预计降雪 {amount}cm")

    if lang != 'en':
        return title, body

    # 私信：标题是昵称、文字消息是原文；只翻译图片 / 其他类型的占位文案
    if data.get('type') == 'message':
        mtype = data.get('messageType')
        if mtype == 'image':
            return title, 'Sent a photo'
        if mtype and mtype != 'text':
            return title, 'Sent a message'
        return title, body

    key = data.get('template_key') or TYPE_TO_TEMPLATE.get(data.get('type') or '') \
        or TYPE_TO_TEMPLATE.get(notification_type or '')
    if key not in EN_TEMPLATES:
        return title, body
    en_title, en_body = EN_TEMPLATES[key]

    if key in ('notifTennisActivityCommentRoot', 'notifTennisActivityCommentReply', 'notifTennisActivityComment'):
        actor = params.get('actor_name')
        if actor:
            en_title = f'{actor} replied to you' if key.endswith('Reply') else f'{actor} commented on your match'
        en_body = params.get('preview') or body      # 评论内容原文
    elif key == 'notifTennisActivityNearby':
        host, court, mode = params.get('host_name'), params.get('court_name'), params.get('mode')
        if host and court and mode:
            en_body = f"{host} is hosting a {EN_TENNIS_MODES.get(mode, mode)} at {court}"

    return en_title, en_body


# =====================================================
# 发送
# =====================================================

def _stringify_data(data: Optional[Dict]) -> Dict[str, str]:
    """FCM data 只能是 str→str。dict / list 用 JSON 序列化。"""
    out: Dict[str, str] = {}
    for key, value in (data or {}).items():
        if value is None:
            continue
        if isinstance(value, str):
            out[key] = value
        elif isinstance(value, (dict, list)):
            out[key] = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        elif isinstance(value, bool):
            out[key] = 'true' if value else 'false'
        else:
            out[key] = str(value)
    return out


def _is_invalid_token_error(exc: Exception) -> bool:
    if isinstance(exc, (messaging.UnregisteredError, messaging.SenderIdMismatchError)):
        return True
    if isinstance(exc, fb_exceptions.InvalidArgumentError):
        msg = str(exc).lower()
        return 'registration token' in msg or 'not a valid fcm' in msg
    return False


def _build_message(token: str, title: str, body: str, data: Dict[str, str],
                   badge: Optional[int], thread_id: Optional[str],
                   image_url: Optional[str]) -> messaging.Message:
    return messaging.Message(
        token=token,
        notification=messaging.Notification(title=title, body=body, image=image_url),
        data=data,
        apns=messaging.APNSConfig(
            headers={'apns-priority': '10'},
            payload=messaging.APNSPayload(
                aps=messaging.Aps(
                    alert=messaging.ApsAlert(title=title, body=body),
                    badge=badge,               # None = 不改角标
                    sound='default',
                    thread_id=thread_id,       # 同类通知在通知中心分组
                ),
            ),
        ),
        android=messaging.AndroidConfig(
            priority='high',
            notification=messaging.AndroidNotification(
                icon='ic_notification',
                color='#8B5CF6',
                sound='default',
                channel_id='high_importance_channel',
                notification_count=badge,
            ),
        ),
    )


def send_to_users(
    user_ids: List[str],
    title: str,
    body: str,
    data: Optional[Dict] = None,
    notification_type: Optional[str] = None,
    image_url: Optional[str] = None,
) -> Dict:
    """
    给一组用户的所有设备发推送，按设备 locale 渲染文案、按用户设置角标。

    返回:
      {
        'device_count', 'success_count', 'failure_count',
        'invalid_count'   —— token 失效已删除（不需要重试）
        'retryable_count' —— 临时错误（FCM 不可用 / 限流 / 网络），调用方可重试
        'errors'          —— 前几条错误信息
      }
    """
    data = dict(data or {})
    result = {'device_count': 0, 'success_count': 0, 'failure_count': 0,
              'invalid_count': 0, 'retryable_count': 0, 'errors': []}

    devices = get_user_devices(user_ids)
    result['device_count'] = len(devices)
    if not devices:
        return result

    initialize_firebase()
    badges = get_badge_counts([d['user_id'] for d in devices])
    string_data = _stringify_data(data)
    thread_id = data.get('type') or notification_type

    messages, tokens = [], []
    for d in devices:
        t, b = render_for_locale(d.get('locale'), notification_type, data, title or '', body or '')
        messages.append(_build_message(d['token'], t, b, string_data,
                                       badges.get(d['user_id']), thread_id, image_url))
        tokens.append(d['token'])

    invalid_tokens = []
    for i in range(0, len(messages), FCM_BATCH_SIZE):
        batch_tokens = tokens[i:i + FCM_BATCH_SIZE]
        try:
            batch = messaging.send_each(messages[i:i + FCM_BATCH_SIZE])
        except Exception as e:                     # 整批失败（鉴权 / 网络）→ 全部可重试
            print(f"❌ send_each 整批失败: {e}")
            result['failure_count'] += len(batch_tokens)
            result['retryable_count'] += len(batch_tokens)
            result['errors'].append(str(e))
            continue

        for token, resp in zip(batch_tokens, batch.responses):
            if resp.success:
                result['success_count'] += 1
                continue
            result['failure_count'] += 1
            exc = resp.exception
            if _is_invalid_token_error(exc):
                result['invalid_count'] += 1
                invalid_tokens.append(token)
                print(f"   → token 失效 {mask_token(token)}: {type(exc).__name__}")
            else:
                result['retryable_count'] += 1
                print(f"   → 发送失败 {mask_token(token)}: {type(exc).__name__}: {exc}")
                if len(result['errors']) < 5:
                    result['errors'].append(f'{type(exc).__name__}: {exc}')

    delete_invalid_tokens(invalid_tokens)
    print(f"📤 设备 {result['device_count']}，成功 {result['success_count']}，"
          f"失效 {result['invalid_count']}，可重试 {result['retryable_count']}")
    return result


def send_push_notification(
    tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict] = None,
    image_url: Optional[str] = None,
) -> Dict:
    """
    直接按 token 发送（诊断/测试用，不做多语言和角标）。
    业务代码请用 send_to_users。
    """
    if not tokens:
        return {'success_count': 0, 'failure_count': 0}
    initialize_firebase()
    string_data = _stringify_data(data)
    messages = [_build_message(t, title, body, string_data, None, None, image_url) for t in tokens]
    success, failure, invalid = 0, 0, []
    for i in range(0, len(messages), FCM_BATCH_SIZE):
        batch = messaging.send_each(messages[i:i + FCM_BATCH_SIZE])
        for token, resp in zip(tokens[i:i + FCM_BATCH_SIZE], batch.responses):
            if resp.success:
                success += 1
            else:
                failure += 1
                if _is_invalid_token_error(resp.exception):
                    invalid.append(token)
    delete_invalid_tokens(invalid)
    return {'success_count': success, 'failure_count': failure}


def healthcheck() -> Dict:
    """
    不给任何人推送的前提下检查凭证：
      supabase —— 调一次 push_badge_counts([])
      firebase —— dry_run 发给一个假 token：凭证有效时 FCM 返回 InvalidArgument（token 无效），
                  凭证无效时返回鉴权错误 / 私钥解析失败
    """
    out: Dict = {}
    try:
        sb_rpc('push_badge_counts', {'p_user_ids': []})
        out['supabase'] = 'ok'
    except Exception as e:
        out['supabase'] = f'error: {type(e).__name__}: {e}'
    try:
        # 空数组：只验证 RPC 存在且有权限，不会移动任何 token（迁移 157 之前会报错）
        sb_rpc('retire_device_tokens', {'p_tokens': [], 'p_reason': 'healthcheck'})
        out['retire_rpc'] = 'ok'
    except Exception as e:
        out['retire_rpc'] = f'missing/error: {type(e).__name__}'
    try:
        initialize_firebase()
        messaging.send(messaging.Message(token='healthcheck-invalid-token', data={'ping': '1'}), dry_run=True)
        out['firebase'] = 'ok'
    except (fb_exceptions.InvalidArgumentError, messaging.UnregisteredError):
        out['firebase'] = 'ok'          # 鉴权通过，只是 token 是假的
    except Exception as e:
        out['firebase'] = f'error: {type(e).__name__}: {str(e)[:200]}'
    return out


# =====================================================
# 降雪提醒
# =====================================================

def send_snow_alert_notification(user_ids: List[str], resort_name: str, snow_date,
                                 snow_amount: float, resort_id=None) -> Dict:
    """
    降雪提醒。snow_date 可以是 date / ISO 字符串，或旧调用方传的展示字符串（如 '02月20日'）。
    """
    if isinstance(snow_date, (date, datetime)):
        snow_date_iso = snow_date.isoformat()[:10]
        zh_date = f'{snow_date.month:02d}月{snow_date.day:02d}日'
    else:
        snow_date_iso = str(snow_date)
        zh_date = str(snow_date)

    amount = f'{snow_amount:g}' if isinstance(snow_amount, (int, float)) else str(snow_amount)
    data = {
        'type': 'snow_alert',
        'resort_name': resort_name,
        'snow_date': snow_date_iso,
        'snow_amount': amount,
        'template_key': 'notifSnowAlert',
    }
    if resort_id is not None:
        data['resort_id'] = str(resort_id)
    # ISO 日期才能按语言格式化；旧调用方的展示字符串只走中文兜底
    if isinstance(snow_date, (date, datetime)):
        data['template_params'] = {
            'resort_name': resort_name,
            'snow_date_iso': snow_date_iso,
            'snow_amount': amount,
        }

    return send_to_users(
        user_ids=user_ids,
        title=f'❄️ {resort_name} 降雪预报',
        body=f'{zh_date} 预计降雪 {amount}cm',
        data=data,
        notification_type='snow_alert',
    )


if __name__ == '__main__':
    print("Push notification service loaded")
