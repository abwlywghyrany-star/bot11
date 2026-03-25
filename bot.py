#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
🤖 بوت تليغرام - ملازم تعليمية
نظام ديناميكي بإدارة الأدمن مع فحص الاشتراك الإجباري
"""

import html
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from dotenv import load_dotenv
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

# ====================== الإعدادات ======================
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()

if not BOT_TOKEN:
    print("❌ خطأ: لم يتم العثور على BOT_TOKEN!")
    print("📝 أضف BOT_TOKEN في ملف .env")
    sys.exit(1)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

ADMIN_ID = int(os.getenv('ADMIN_ID', '0')) or None
CHANNEL_ID = os.getenv('CHANNEL_ID', '-1001234567890')
REQUIRED_CHANNELS = [
    ch.strip()
    for ch in os.getenv('REQUIRED_CHANNELS', CHANNEL_ID).split(',')
    if ch.strip()
]

DATA_FILE = 'content_store.json'

user_subscriptions = {}
admin_states = {}
active_user_views = {}
content_store = {}


def normalize_channel_identifier(raw: str) -> str:
    """Normalize channel identifier to a Bot API-friendly value."""
    value = (raw or '').strip()
    if not value:
        return value

    lowered = value.lower()
    if lowered.startswith('https://t.me/') or lowered.startswith('http://t.me/'):
        value = value.split('t.me/', 1)[1]
    elif lowered.startswith('t.me/'):
        value = value.split('t.me/', 1)[1]

    value = value.split('?', 1)[0].split('/', 1)[0].strip()
    if not value:
        return value

    if value.startswith('@'):
        return value
    if value.lstrip('-').isdigit():
        return value
    return '@' + value


def channel_join_url(channel: str) -> str | None:
    """Return a public join URL when the channel has a username."""
    channel = normalize_channel_identifier(channel)
    if not channel:
        return None
    if channel.startswith('@'):
        return f"https://t.me/{channel[1:]}"
    return None


REQUIRED_CHANNELS = [normalize_channel_identifier(ch) for ch in REQUIRED_CHANNELS]


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def empty_store() -> dict:
    return {
        'next_id': 1,
        'root_ids': [],
        'nodes': {}
    }


def is_admin(user_id: int) -> bool:
    return ADMIN_ID is not None and user_id == ADMIN_ID


def save_store() -> None:
    temp_path = DATA_FILE + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as file_obj:
        json.dump(content_store, file_obj, ensure_ascii=False, indent=2)
    os.replace(temp_path, DATA_FILE)


def get_node(node_id: str | int | None) -> dict | None:
    if node_id is None:
        return None
    return content_store['nodes'].get(str(node_id))


def create_node(title: str, parent_id: str | None = None) -> dict:
    cleaned_title = ' '.join((title or '').split()).strip()
    if not cleaned_title:
        raise ValueError('اسم القسم لا يمكن أن يكون فارغاً.')

    if parent_id is not None:
        parent = get_node(parent_id)
        if not parent:
            raise ValueError('القسم الأب غير موجود.')
        if parent.get('file'):
            raise ValueError('هذا المستوى مرتبط بملف. احذف الملف أولاً إذا تريد تضيف مستويات تحته.')

    node_id = str(content_store['next_id'])
    content_store['next_id'] += 1

    node = {
        'id': node_id,
        'title': cleaned_title,
        'parent_id': str(parent_id) if parent_id is not None else None,
        'child_ids': [],
        'file': None,
        'created_at': now_iso(),
        'updated_at': now_iso(),
    }
    content_store['nodes'][node_id] = node

    if parent_id is None:
        content_store['root_ids'].append(node_id)
    else:
        parent = get_node(parent_id)
        parent['child_ids'].append(node_id)
        parent['updated_at'] = now_iso()

    save_store()
    return node


def load_store() -> None:
    global content_store

    if not os.path.exists(DATA_FILE):
        content_store = empty_store()
        save_store()
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as file_obj:
            loaded = json.load(file_obj)
        if not isinstance(loaded, dict):
            raise ValueError('صيغة التخزين غير صحيحة')

        content_store = {
            'next_id': int(loaded.get('next_id', 1)),
            'root_ids': [str(node_id) for node_id in loaded.get('root_ids', [])],
            'nodes': {
                str(node_id): node
                for node_id, node in loaded.get('nodes', {}).items()
                if isinstance(node, dict)
            },
        }
    except Exception as exc:
        logger.error(f'❌ تعذر قراءة ملف التخزين: {exc}')
        content_store = empty_store()
        save_store()


def get_children(node_id: str | int) -> list[dict]:
    node = get_node(node_id)
    if not node:
        return []
    children = []
    for child_id in node.get('child_ids', []):
        child = get_node(child_id)
        if child:
            children.append(child)
    return children


def get_path_nodes(node_id: str | int) -> list[dict]:
    node = get_node(node_id)
    path_nodes = []
    while node:
        path_nodes.append(node)
        parent_id = node.get('parent_id')
        node = get_node(parent_id) if parent_id else None
    path_nodes.reverse()
    return path_nodes


def format_path(node_id: str | int) -> str:
    path_nodes = get_path_nodes(node_id)
    if not path_nodes:
        return 'الرئيسية'
    return ' / '.join(html.escape(node['title']) for node in path_nodes)


def rename_node(node_id: str | int, new_title: str) -> dict:
    node = get_node(node_id)
    if not node:
        raise ValueError('القسم غير موجود.')
    cleaned_title = ' '.join((new_title or '').split()).strip()
    if not cleaned_title:
        raise ValueError('الاسم الجديد لا يمكن أن يكون فارغاً.')
    node['title'] = cleaned_title
    node['updated_at'] = now_iso()
    save_store()
    return node


def attach_telegram_file(node_id: str | int, display_name: str, document) -> dict:
    node = get_node(node_id)
    if not node:
        raise ValueError('القسم غير موجود.')
    if node.get('child_ids'):
        raise ValueError('لا يمكن ربط ملف بقسم يحتوي على مستويات فرعية.')

    cleaned_name = ' '.join((display_name or '').split()).strip() or document.file_name or 'ملف بدون اسم'
    node['file'] = {
        'source': 'telegram',
        'name': cleaned_name,
        'file_id': document.file_id,
        'telegram_file_name': document.file_name,
        'mime_type': document.mime_type,
        'uploaded_at': now_iso(),
    }
    node['updated_at'] = now_iso()
    save_store()
    return node


def remove_file(node_id: str | int) -> dict:
    node = get_node(node_id)
    if not node:
        raise ValueError('القسم غير موجود.')
    node['file'] = None
    node['updated_at'] = now_iso()
    save_store()
    return node


def delete_node_recursive(node_id: str | int) -> None:
    node = get_node(node_id)
    if not node:
        raise ValueError('القسم غير موجود.')

    for child_id in list(node.get('child_ids', [])):
        delete_node_recursive(child_id)

    parent_id = node.get('parent_id')
    if parent_id:
        parent = get_node(parent_id)
        if parent and str(node_id) in parent.get('child_ids', []):
            parent['child_ids'].remove(str(node_id))
            parent['updated_at'] = now_iso()
    else:
        if str(node_id) in content_store['root_ids']:
            content_store['root_ids'].remove(str(node_id))

    content_store['nodes'].pop(str(node_id), None)
    save_store()


def get_counts() -> tuple[int, int]:
    nodes_count = len(content_store['nodes'])
    files_count = sum(1 for node in content_store['nodes'].values() if node.get('file'))
    return nodes_count, files_count


def first_public_channel_url() -> str | None:
    for channel in REQUIRED_CHANNELS:
        url = channel_join_url(channel)
        if url:
            return url
    return None


class HealthcheckHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for Replit/UptimeRobot keep-alive checks."""

    def _send_health_response(self, include_body: bool):
        path = (self.path or '/').split('?', 1)[0].rstrip('/') or '/'
        if path not in ['/', '/health']:
            self.send_response(404)
            self.end_headers()
            return

        nodes_count, files_count = get_counts()
        payload = {
            'status': 'ok',
            'service': 'telegram-bot',
            'time': now_iso(),
            'nodes': nodes_count,
            'files': files_count,
        }
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        if include_body:
            self.wfile.write(body)

    def do_GET(self):
        self._send_health_response(include_body=True)

    def do_HEAD(self):
        self._send_health_response(include_body=False)

    def log_message(self, format, *args):
        return


def start_keep_alive_server() -> None:
    """Start a lightweight HTTP server so UptimeRobot can ping the Replit app."""
    host = os.getenv('KEEP_ALIVE_HOST', '0.0.0.0').strip() or '0.0.0.0'
    port_value = os.getenv('PORT', os.getenv('KEEP_ALIVE_PORT', '8080')).strip() or '8080'

    try:
        port = int(port_value)
    except ValueError:
        logger.warning(f'⚠️ قيمة PORT غير صالحة: {port_value}, سيتم استخدام 8080')
        port = 8080

    def serve_forever():
        try:
            server = ThreadingHTTPServer((host, port), HealthcheckHandler)
            logger.info(f'🌐 خادم keep-alive يعمل على http://{host}:{port}/health')
            server.serve_forever()
        except Exception as exc:
            logger.error(f'❌ تعذر تشغيل خادم keep-alive: {exc}')

    server_thread = threading.Thread(target=serve_forever, daemon=True, name='keepalive-server')
    server_thread.start()


def clear_admin_state(user_id: int) -> None:
    admin_states.pop(user_id, None)


def set_admin_state(user_id: int, **state) -> None:
    admin_states[user_id] = state


def remember_user_view(user_id: int, chat_id: int, message_id: int, first_name: str | None, node_id: str | None) -> None:
    active_user_views[user_id] = {
        'chat_id': chat_id,
        'message_id': message_id,
        'first_name': first_name,
        'node_id': str(node_id) if node_id is not None else None,
    }


def clear_user_view(user_id: int) -> None:
    active_user_views.pop(user_id, None)


def refresh_active_user_views() -> None:
    stale_users = []

    for user_id, view in list(active_user_views.items()):
        if is_admin(user_id):
            continue

        chat_id = view['chat_id']
        message_id = view['message_id']
        first_name = view.get('first_name')
        node_id = view.get('node_id')

        try:
            if node_id and get_node(node_id):
                safe_edit_message(
                    chat_id,
                    message_id,
                    get_user_node_text(node_id),
                    build_user_node_keyboard(node_id, user_id),
                )
            else:
                safe_edit_message(
                    chat_id,
                    message_id,
                    get_home_text(first_name),
                    build_main_keyboard(user_id),
                )
                active_user_views[user_id]['node_id'] = None
        except Exception as exc:
            logger.warning(f'⚠️ تعذر تحديث واجهة المستخدم {user_id}: {exc}')
            stale_users.append(user_id)

    for user_id in stale_users:
        clear_user_view(user_id)


def get_subscription_message() -> str:
    lines = []
    for channel in REQUIRED_CHANNELS:
        url = channel_join_url(channel)
        if url:
            lines.append(f"🔗 <a href='{url}'>اضغط هنا للاشتراك</a>")
        else:
            lines.append(f"📢 {html.escape(channel)}")
    channels_text = '\n'.join(lines) if lines else '📢 لا توجد قنوات مطلوبة حالياً'

    return f"""
<b>📌 اشتراك إجباري مطلوب</b>

للوصول إلى جميع الملفات والخدمات، يجب الاشتراك في القنوات التالية:

{channels_text}

<b>⏭️ بعد الاشتراك:</b>
اضغط على زر ✅ <b>تحقق من الاشتراك</b>
"""


def get_subscription_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    for channel in REQUIRED_CHANNELS:
        url = channel_join_url(channel)
        if url:
            markup.add(InlineKeyboardButton(text='📢 اضغط للاشتراك', url=url))
    markup.add(InlineKeyboardButton(text='✅ تحقق من الاشتراك', callback_data='check_subscription'))
    return markup


def verify_subscription(user_id, chat_id):
    """التحقق الفعلي من اشتراك المستخدم في جميع القنوات المطلوبة."""
    if is_admin(user_id):
        return True

    try:
        logger.info(f"🔍 جاري التحقق من اشتراك المستخدم {user_id} في القنوات: {REQUIRED_CHANNELS}")

        for channel in REQUIRED_CHANNELS:
            try:
                channel_id = normalize_channel_identifier(channel)
                logger.info(f"   📢 التحقق من القناة: {channel_id}")

                try:
                    member = bot.get_chat_member(channel_id, user_id)
                    logger.info(f"   ✅ تم الحصول على معلومات العضوية: الحالة = {member.status}")

                    if member.status in ['member', 'administrator', 'creator']:
                        logger.info(f"   ✅ المستخدم {user_id} عضو في {channel_id}")
                        continue
                    if member.status == 'restricted' and getattr(member, 'is_member', False):
                        logger.info(f"   ✅ المستخدم {user_id} عضو مقيد لكن له وصول في {channel_id}")
                        continue
                    if member.status == 'left':
                        logger.warning(f"   ❌ المستخدم {user_id} غير مشترك في {channel_id}")
                        return False
                    if member.status == 'kicked':
                        logger.warning(f"   ❌ المستخدم {user_id} محظور من {channel_id}")
                        return False

                    logger.warning(f"   ⚠️ حالة غير متوقعة: {member.status}")
                    return False

                except telebot.apihelper.ApiTelegramException as api_error:
                    error_str = str(api_error).lower()
                    logger.warning(f"   ⚠️ خطأ API: {api_error}")

                    if 'chat not found' in error_str or 'channel not found' in error_str:
                        logger.error(f"   ❌ القناة {channel_id} غير موجودة/غير قابلة للوصول")
                        return False
                    if 'bot was kicked' in error_str or 'bot is not a member' in error_str:
                        logger.error(f"   ❌ البوت ليس عضواً في القناة {channel_id}! أضف البوت كمسؤول ثم جرّب.")
                        return False
                    if 'not a member' in error_str:
                        logger.warning(f"   ❌ المستخدم {user_id} ليس عضواً في {channel_id}")
                        return False

                    logger.error(f"   ❌ خطأ في التحقق: {api_error}")
                    return False

            except Exception as channel_error:
                logger.error(f"   ❌ خطأ غير متوقع للقناة {channel}: {channel_error}")
                return False

        user_subscriptions[user_id] = {
            'verified': True,
            'timestamp': now_iso(),
        }
        logger.info(f"✅ تم التحقق بنجاح من اشتراك المستخدم {user_id}")
        return True

    except Exception as exc:
        logger.error(f"❌ خطأ عام في التحقق من الاشتراك: {exc}")
        return False


def check_subscription(user_id, chat_id):
    if user_id in user_subscriptions:
        return verify_subscription(user_id, chat_id)
    return verify_subscription(user_id, chat_id)


def build_main_keyboard(user_id: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    for root_id in content_store['root_ids']:
        node = get_node(root_id)
        if node:
            markup.add(InlineKeyboardButton(text=node['title'], callback_data=f'usr_{node["id"]}'))

    markup.add(InlineKeyboardButton(text='🆘 مساعدة', callback_data='help'))

    channel_url = first_public_channel_url()
    if channel_url:
        markup.add(InlineKeyboardButton(text='📢 القناة', url=channel_url))

    if is_admin(user_id):
        markup.add(InlineKeyboardButton(text='⚙️ لوحة الأدمن', callback_data='adm_root'))
    return markup


def build_user_node_keyboard(node_id: str, user_id: int) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    node = get_node(node_id)
    if not node:
        return build_main_keyboard(user_id)

    for child in get_children(node_id):
        markup.add(InlineKeyboardButton(text=child['title'], callback_data=f'usr_{child["id"]}'))

    parent_id = node.get('parent_id')
    if parent_id:
        markup.add(
            InlineKeyboardButton(text='🔙 رجوع', callback_data=f'usr_{parent_id}'),
            InlineKeyboardButton(text='🏠 الرئيسية', callback_data='usr_root')
        )
    else:
        markup.add(InlineKeyboardButton(text='🏠 الرئيسية', callback_data='usr_root'))

    if is_admin(user_id):
        markup.add(InlineKeyboardButton(text='⚙️ لوحة الأدمن', callback_data=f'adm_open_{node_id}'))

    return markup


def build_admin_root_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    for root_id in content_store['root_ids']:
        node = get_node(root_id)
        if node:
            markup.add(InlineKeyboardButton(text=f'📁 {node["title"]}', callback_data=f'adm_open_{node["id"]}'))

    markup.add(InlineKeyboardButton(text='➕ إضافة قسم رئيسي', callback_data='adm_addroot'))
    markup.add(InlineKeyboardButton(text='👁 معاينة واجهة الطالب', callback_data='usr_root'))
    return markup


def build_admin_node_keyboard(node_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    node = get_node(node_id)
    if not node:
        return build_admin_root_keyboard()

    for child in get_children(node_id):
        markup.add(InlineKeyboardButton(text=f'📁 {child["title"]}', callback_data=f'adm_open_{child["id"]}'))

    markup.add(
        InlineKeyboardButton(text='➕ إضافة مستوى', callback_data=f'adm_add_{node_id}'),
        InlineKeyboardButton(text='✏️ تعديل الاسم', callback_data=f'adm_ren_{node_id}')
    )

    if node.get('child_ids'):
        markup.add(InlineKeyboardButton(text='ℹ️ هذا القسم يحتوي مستويات فرعية', callback_data='noop'))
    else:
        file_button_text = '📎 استبدال الملف' if node.get('file') else '📎 ربط ملف PDF'
        markup.add(InlineKeyboardButton(text=file_button_text, callback_data=f'adm_fil_{node_id}'))
        if node.get('file'):
            markup.add(InlineKeyboardButton(text='🗑 حذف الملف', callback_data=f'adm_rmf_{node_id}'))

    markup.add(InlineKeyboardButton(text='❌ حذف هذا القسم', callback_data=f'adm_del_{node_id}'))

    parent_id = node.get('parent_id')
    if parent_id:
        markup.add(
            InlineKeyboardButton(text='🔙 رجوع', callback_data=f'adm_open_{parent_id}'),
            InlineKeyboardButton(text='🏠 الجذر', callback_data='adm_root')
        )
    else:
        markup.add(InlineKeyboardButton(text='🏠 الجذر', callback_data='adm_root'))

    return markup


def build_delete_confirmation_keyboard(node_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton(text='✅ نعم، احذف', callback_data=f'adm_cdel_{node_id}'),
        InlineKeyboardButton(text='❎ لا', callback_data=f'adm_open_{node_id}')
    )
    return markup


def get_home_text(first_name: str | None) -> str:
    safe_name = html.escape(first_name or 'عزيزي')
    nodes_count, files_count = get_counts()
    if not content_store['root_ids']:
        body = 'لا يوجد محتوى منشور حالياً. إذا كنت الأدمن استخدم /admin لبناء الهيكل.'
    else:
        body = 'اختر القسم المناسب من الأزرار أدناه.'

    return f"""
<b>👋 أهلاً {safe_name}!</b>

{body}

<b>📊 الإحصائيات:</b>
• عدد الأقسام: {nodes_count}
• عدد الملفات: {files_count}
"""


def get_user_node_text(node_id: str) -> str:
    node = get_node(node_id)
    if not node:
        return '<b>❌ هذا القسم غير موجود.</b>'

    children_count = len(node.get('child_ids', []))
    file_meta = node.get('file')

    if children_count:
        action_line = 'اختر المستوى التالي:'
    elif file_meta:
        action_line = 'هذا مستوى نهائي. اضغط عليه وسيتم إرسال الملف مباشرة.'
    else:
        action_line = 'هذا القسم فارغ حالياً.'

    return f"""
<b>📂 {html.escape(node['title'])}</b>

<b>المسار:</b>
{format_path(node_id)}

{action_line}
"""


def get_admin_root_text() -> str:
    nodes_count, files_count = get_counts()
    return f"""
<b>⚙️ لوحة الأدمن</b>

من هنا تقدر تبني الهيكل كامل من داخل البوت:
• إضافة أقسام رئيسية
• إضافة مستويات فرعية بلا حدود
• ربط ملفات PDF بالمستويات النهائية
• تعديل أو حذف أي جزء لاحقاً

<b>📊 الإحصائيات الحالية:</b>
• عدد الأقسام: {nodes_count}
• عدد الملفات: {files_count}
"""


def get_admin_node_text(node_id: str) -> str:
    node = get_node(node_id)
    if not node:
        return '<b>❌ هذا القسم غير موجود.</b>'

    file_meta = node.get('file')
    file_line = 'لا يوجد ملف مرتبط'
    if file_meta:
        file_line = f"ملف مرتبط: {html.escape(file_meta.get('name', 'بدون اسم'))}"

    return f"""
<b>⚙️ إدارة قسم</b>

<b>الاسم:</b> {html.escape(node['title'])}
<b>المسار:</b> {format_path(node_id)}
<b>عدد المستويات الفرعية:</b> {len(node.get('child_ids', []))}
<b>حالة الملف:</b> {file_line}

اختر الإجراء المناسب من الأزرار أدناه.
"""


def send_user_home(chat_id: int, user_id: int, first_name: str | None, message_id: int | None = None) -> None:
    text = get_home_text(first_name)
    markup = build_main_keyboard(user_id)
    if message_id:
        safe_edit_message(chat_id, message_id, text, markup)
        remember_user_view(user_id, chat_id, message_id, first_name, None)
    else:
        sent_message = bot.send_message(chat_id, text, reply_markup=markup)
        remember_user_view(user_id, chat_id, sent_message.message_id, first_name, None)


def send_admin_root(chat_id: int, message_id: int | None = None) -> None:
    text = get_admin_root_text()
    markup = build_admin_root_keyboard()
    if message_id:
        safe_edit_message(chat_id, message_id, text, markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def send_admin_node(chat_id: int, node_id: str, message_id: int | None = None) -> None:
    text = get_admin_node_text(node_id)
    markup = build_admin_node_keyboard(node_id)
    if message_id:
        safe_edit_message(chat_id, message_id, text, markup)
    else:
        bot.send_message(chat_id, text, reply_markup=markup)


def safe_edit_message(chat_id: int, message_id: int, text: str, markup: InlineKeyboardMarkup | None = None) -> None:
    try:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    except telebot.apihelper.ApiTelegramException as exc:
        if 'message is not modified' in str(exc).lower():
            logger.info('ℹ️ لم يتم تعديل الرسالة لأن المحتوى لم يتغير')
            return
        raise


def send_user_node(chat_id: int, user_id: int, first_name: str | None, node_id: str, message_id: int | None = None) -> None:
    text = get_user_node_text(node_id)
    markup = build_user_node_keyboard(node_id, user_id)
    if message_id:
        safe_edit_message(chat_id, message_id, text, markup)
        remember_user_view(user_id, chat_id, message_id, first_name, node_id)
    else:
        sent_message = bot.send_message(chat_id, text, reply_markup=markup)
        remember_user_view(user_id, chat_id, sent_message.message_id, first_name, node_id)


def send_node_file(chat_id: int, node: dict) -> tuple[bool, str]:
    file_meta = node.get('file')
    if not file_meta:
        return False, 'لا يوجد ملف مرتبط بهذا القسم.'

    caption = f"<b>📄 {html.escape(file_meta.get('name', node['title']))}</b>\n✅ تم الإرسال بنجاح"
    source = file_meta.get('source')

    try:
        if source == 'telegram':
            bot.send_document(chat_id, file_meta['file_id'], caption=caption)
            return True, 'تم إرسال الملف.'

        if source == 'local':
            file_path = file_meta.get('path', '')
            if not os.path.isfile(file_path):
                return False, f'الملف المحلي غير موجود: {file_path}'
            with open(file_path, 'rb') as file_obj:
                bot.send_document(chat_id, file_obj, caption=caption)
            return True, 'تم إرسال الملف.'

        return False, 'مصدر الملف غير معروف.'
    except Exception as exc:
        logger.error(f'❌ تعذر إرسال الملف للقسم {node["id"]}: {exc}')
        return False, 'حدث خطأ أثناء إرسال الملف.'


def prompt_subscription(chat_id: int) -> None:
    bot.send_message(chat_id, get_subscription_message(), reply_markup=get_subscription_markup())


def enforce_subscription(
    user_id: int,
    chat_id: int,
    first_name: str | None = None,
    *,
    message_id: int | None = None,
    callback_id: str | None = None,
) -> bool:
    if check_subscription(user_id, chat_id):
        return True

    clear_user_view(user_id)

    if callback_id:
        bot.answer_callback_query(callback_id, '❌ يجب الاشتراك أولاً', show_alert=True)

    if message_id:
        safe_edit_message(chat_id, message_id, get_subscription_message(), get_subscription_markup())
    else:
        prompt_subscription(chat_id)

    return False


@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not enforce_subscription(user_id, chat_id, message.from_user.first_name):
        return

    send_user_home(chat_id, user_id, message.from_user.first_name)
    logger.info(f'✅ بدء البوت للمستخدم {user_id}')


@bot.message_handler(commands=['help'])
def handle_help(message):
    if not is_admin(message.from_user.id):
        if not enforce_subscription(message.from_user.id, message.chat.id, message.from_user.first_name):
            return

    help_text = """
<b>🆘 المساعدة</b>

<b>طريقة الاستخدام للطالب:</b>
1️⃣ اضغط على القسم المناسب
2️⃣ استمر داخل الأزرار المتداخلة
3️⃣ عند الوصول للمستوى النهائي سيتم إرسال الملف مباشرة

<b>الأوامر:</b>
/start - الرئيسية
/help - المساعدة
/about - عن البوت

<b>للأدمن فقط:</b>
/admin - لوحة التحكم
/cancel - إلغاء العملية الحالية
"""
    bot.send_message(message.chat.id, help_text, reply_markup=build_main_keyboard(message.from_user.id))


@bot.message_handler(commands=['about'])
def handle_about(message):
    if not is_admin(message.from_user.id):
        if not enforce_subscription(message.from_user.id, message.chat.id, message.from_user.first_name):
            return

    nodes_count, files_count = get_counts()
    about_text = f"""
<b>📋 عن البوت</b>

🤖 <b>بوت الملازم التعليمية</b>
👨‍💻 المطور: @jih_313
إصدار: 3.0
آخر تحديث: {datetime.now().strftime('%Y-%m-%d')}

<b>المميزات:</b>
✅ إدارة ديناميكية كاملة من داخل تيليغرام
✅ أزرار متداخلة بلا تعديل كود
✅ ربط ملفات PDF بالمستويات النهائية
✅ فحص اشتراك إجباري

<b>الإحصائيات الحالية:</b>
• عدد الأقسام: {nodes_count}
• عدد الملفات: {files_count}
"""
    bot.send_message(message.chat.id, about_text, reply_markup=build_main_keyboard(message.from_user.id))


@bot.message_handler(commands=['admin'])
def handle_admin(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, '❌ هذا الأمر مخصص للأدمن فقط.')
        return
    clear_admin_state(message.from_user.id)
    send_admin_root(message.chat.id)


@bot.message_handler(commands=['cancel'])
def handle_cancel(message):
    clear_admin_state(message.from_user.id)
    if is_admin(message.from_user.id):
        bot.reply_to(message, '✅ تم إلغاء العملية الحالية.')
        send_admin_root(message.chat.id)
    else:
        bot.reply_to(message, 'لا توجد عملية نشطة.')


@bot.callback_query_handler(func=lambda call: call.data == 'check_subscription')
def handle_check_subscription(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    user_name = call.from_user.first_name or 'مستخدم'

    bot.answer_callback_query(call.id, '⏳ جاري التحقق من الاشتراك...', show_alert=False)
    is_subscribed = verify_subscription(user_id, chat_id)
    logger.info(f'📊 نتيجة التحقق للمستخدم {user_id}: {is_subscribed}')

    if is_subscribed:
        success_message = f"""
✅ <b>شكراً {html.escape(user_name)}!</b>

تم التحقق من اشتراكك بنجاح.
اختر القسم المناسب من القائمة.
"""
        try:
            safe_edit_message(chat_id, call.message.message_id, success_message, build_main_keyboard(user_id))
            remember_user_view(user_id, chat_id, call.message.message_id, call.from_user.first_name, None)
            bot.answer_callback_query(call.id, '✅ تم التحقق بنجاح!', show_alert=True)
        except Exception as exc:
            logger.error(f'❌ خطأ في تحديث الرسالة: {exc}')
            bot.answer_callback_query(call.id, '✅ تم التحقق بنجاح!', show_alert=True)
    else:
        clear_user_view(user_id)
        try:
            safe_edit_message(chat_id, call.message.message_id, get_subscription_message(), get_subscription_markup())
        except Exception as exc:
            logger.error(f'❌ خطأ في تحديث الرسالة: {exc}')
        bot.answer_callback_query(call.id, '❌ الاشتراك غير مكتمل بعد.', show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == 'noop')
def handle_noop(call):
    bot.answer_callback_query(call.id, 'ℹ️ احذف المستويات الفرعية أولاً إذا تريد تحويله إلى مستوى نهائي.', show_alert=False)


@bot.callback_query_handler(func=lambda call: call.data == 'help')
def handle_help_button(call):
    if not is_admin(call.from_user.id):
        if not enforce_subscription(
            call.from_user.id,
            call.message.chat.id,
            call.from_user.first_name,
            message_id=call.message.message_id,
            callback_id=call.id,
        ):
            return

    bot.answer_callback_query(call.id)
    help_text = """
<b>🆘 المساعدة</b>

للطلاب:
• تنقّل داخل الأزرار حتى تصل للمستوى النهائي
• عند الضغط على المستوى النهائي يصلك الملف مباشرة

للأدمن:
• استخدم /admin لبناء الهيكل
• أضف المستويات أولاً ثم اربط ملف PDF بالنهاية
• أرسل اسم الملف كنص ثم أرسل الـ PDF أو أرسل الـ PDF مع Caption
"""
    safe_edit_message(call.message.chat.id, call.message.message_id, help_text, build_main_keyboard(call.from_user.id))


@bot.callback_query_handler(func=lambda call: call.data.startswith('usr_'))
def handle_user_navigation(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if not enforce_subscription(
        user_id,
        chat_id,
        call.from_user.first_name,
        message_id=call.message.message_id,
        callback_id=call.id,
    ):
        return

    if call.data == 'usr_root':
        bot.answer_callback_query(call.id)
        send_user_home(chat_id, user_id, call.from_user.first_name, call.message.message_id)
        return

    node_id = call.data.split('_', 1)[1]
    node = get_node(node_id)
    if not node:
        bot.answer_callback_query(call.id, '❌ هذا القسم لم يعد موجوداً.', show_alert=True)
        send_user_home(chat_id, user_id, call.from_user.first_name, call.message.message_id)
        return

    if node.get('child_ids'):
        bot.answer_callback_query(call.id)
        send_user_node(chat_id, user_id, call.from_user.first_name, node_id, call.message.message_id)
        return

    success, info_message = send_node_file(chat_id, node)
    bot.answer_callback_query(call.id, ('✅ ' if success else '❌ ') + info_message, show_alert=not success)


@bot.callback_query_handler(func=lambda call: call.data.startswith('adm_'))
def handle_admin_callbacks(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if not is_admin(user_id):
        bot.answer_callback_query(call.id, '❌ هذا الخيار للأدمن فقط.', show_alert=True)
        return

    data = call.data
    bot.answer_callback_query(call.id)

    if data == 'adm_root':
        clear_admin_state(user_id)
        send_admin_root(chat_id, call.message.message_id)
        return

    if data == 'adm_addroot':
        set_admin_state(user_id, action='create_node', parent_id=None)
        bot.send_message(chat_id, '✍️ أرسل الآن اسم القسم الرئيسي الجديد.')
        return

    if data.startswith('adm_open_'):
        node_id = data.split('_', 2)[2]
        if not get_node(node_id):
            bot.send_message(chat_id, '❌ هذا القسم لم يعد موجوداً.')
            send_admin_root(chat_id, call.message.message_id)
            return
        clear_admin_state(user_id)
        send_admin_node(chat_id, node_id, call.message.message_id)
        return

    if data.startswith('adm_add_'):
        node_id = data.split('_', 2)[2]
        node = get_node(node_id)
        if not node:
            bot.send_message(chat_id, '❌ هذا القسم غير موجود.')
            return
        if node.get('file'):
            bot.send_message(chat_id, '❌ هذا المستوى مرتبط بملف. احذف الملف أولاً إذا تريد تضيف مستويات تحته.')
            return
        set_admin_state(user_id, action='create_node', parent_id=node_id)
        bot.send_message(chat_id, f"✍️ أرسل اسم المستوى الجديد داخل: {format_path(node_id)}")
        return

    if data.startswith('adm_ren_'):
        node_id = data.split('_', 2)[2]
        if not get_node(node_id):
            bot.send_message(chat_id, '❌ هذا القسم غير موجود.')
            return
        set_admin_state(user_id, action='rename_node', node_id=node_id)
        bot.send_message(chat_id, f"✍️ أرسل الاسم الجديد للقسم:\n{format_path(node_id)}")
        return

    if data.startswith('adm_fil_'):
        node_id = data.split('_', 2)[2]
        node = get_node(node_id)
        if not node:
            bot.send_message(chat_id, '❌ هذا القسم غير موجود.')
            return
        if node.get('child_ids'):
            bot.send_message(chat_id, '❌ لا يمكن ربط ملف بقسم يحتوي مستويات فرعية. اختر مستوى نهائي فقط.')
            return
        set_admin_state(user_id, action='await_file', node_id=node_id, pending_title=None)
        bot.send_message(
            chat_id,
            '📎 أرسل اسم الملف كنص ثم أرسل PDF، أو أرسل PDF مباشرة مع Caption ليكون اسم الملف الظاهر للطلاب.'
        )
        return

    if data.startswith('adm_rmf_'):
        node_id = data.split('_', 2)[2]
        try:
            remove_file(node_id)
            bot.send_message(chat_id, '✅ تم حذف الملف المرتبط بهذا القسم.')
            send_admin_node(chat_id, node_id, call.message.message_id)
            refresh_active_user_views()
        except Exception as exc:
            bot.send_message(chat_id, f'❌ {exc}')
        return

    if data.startswith('adm_del_'):
        node_id = data.split('_', 2)[2]
        node = get_node(node_id)
        if not node:
            bot.send_message(chat_id, '❌ هذا القسم غير موجود.')
            return
        warning_text = f"""
<b>⚠️ تأكيد الحذف</b>

سيتم حذف هذا القسم وكل ما بداخله:
{format_path(node_id)}

هل تريد المتابعة؟
"""
        safe_edit_message(chat_id, call.message.message_id, warning_text, build_delete_confirmation_keyboard(node_id))
        return

    if data.startswith('adm_cdel_'):
        node_id = data.split('_', 2)[2]
        node = get_node(node_id)
        if not node:
            bot.send_message(chat_id, '❌ هذا القسم غير موجود.')
            send_admin_root(chat_id, call.message.message_id)
            return
        parent_id = node.get('parent_id')
        try:
            delete_node_recursive(node_id)
            bot.send_message(chat_id, '✅ تم حذف القسم وكل محتواه.')
            if parent_id and get_node(parent_id):
                send_admin_node(chat_id, parent_id, call.message.message_id)
            else:
                send_admin_root(chat_id, call.message.message_id)
            refresh_active_user_views()
        except Exception as exc:
            bot.send_message(chat_id, f'❌ {exc}')
        return


@bot.message_handler(func=lambda message: is_admin(message.from_user.id) and admin_states.get(message.from_user.id, {}).get('action') in {'create_node', 'rename_node', 'await_file'})
def handle_admin_text_input(message):
    user_id = message.from_user.id
    state = admin_states.get(user_id)
    if not state:
        return

    action = state.get('action')
    text = (message.text or '').strip()
    if not text:
        bot.reply_to(message, '❌ النص فارغ. أرسل قيمة صحيحة أو استخدم /cancel.')
        return

    try:
        if action == 'create_node':
            new_node = create_node(text, state.get('parent_id'))
            clear_admin_state(user_id)
            bot.reply_to(message, f'✅ تم إنشاء القسم: {new_node["title"]}')
            send_admin_node(message.chat.id, new_node['id'])
            refresh_active_user_views()
            return

        if action == 'rename_node':
            renamed_node = rename_node(state.get('node_id'), text)
            clear_admin_state(user_id)
            bot.reply_to(message, f'✅ تم تعديل الاسم إلى: {renamed_node["title"]}')
            send_admin_node(message.chat.id, renamed_node['id'])
            refresh_active_user_views()
            return

        if action == 'await_file':
            state['pending_title'] = text
            bot.reply_to(message, '✅ تم حفظ اسم الملف. الآن أرسل ملف PDF.')
            return

    except Exception as exc:
        bot.reply_to(message, f'❌ {exc}')


@bot.message_handler(content_types=['document'], func=lambda message: is_admin(message.from_user.id) and admin_states.get(message.from_user.id, {}).get('action') == 'await_file')
def handle_admin_document_upload(message):
    user_id = message.from_user.id
    state = admin_states.get(user_id)
    if not state:
        return

    document = message.document
    if not document:
        bot.reply_to(message, '❌ لم يتم استلام ملف.')
        return

    file_name = document.file_name or ''
    if not file_name.lower().endswith('.pdf'):
        bot.reply_to(message, '❌ يرجى إرسال ملف PDF فقط.')
        return

    display_name = (message.caption or '').strip() or state.get('pending_title') or file_name

    try:
        node = attach_telegram_file(state.get('node_id'), display_name, document)
        clear_admin_state(user_id)
        bot.reply_to(message, f'✅ تم ربط الملف بالقسم: {node["title"]}')
        send_admin_node(message.chat.id, node['id'])
        refresh_active_user_views()
    except Exception as exc:
        bot.reply_to(message, f'❌ {exc}')


@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if is_admin(user_id) and admin_states.get(user_id):
        bot.reply_to(message, 'ℹ️ أنت داخل عملية إدارة حالياً. أكملها أو استخدم /cancel.')
        return

    if not enforce_subscription(user_id, chat_id, message.from_user.first_name):
        logger.warning(f'⚠️ محاولة وصول من مستخدم غير مشترك: {user_id}')
        return

    send_user_home(chat_id, user_id, message.from_user.first_name)


def main():
    load_store()
    start_keep_alive_server()

    nodes_count, files_count = get_counts()
    logger.info('🚀 جاري بدء البوت...')

    print('\n' + '=' * 70)
    print('✅ البوت يعمل الآن بنجاح!')
    print('=' * 70)
    print('🎯 تفاصيل البوت:')
    print(f'   🤖 عدد الأقسام: {nodes_count}')
    print(f'   📁 عدد الملفات: {files_count}')
    print(f'   📢 القنوات المطلوبة: {len(REQUIRED_CHANNELS)}')
    print(f'   🌐 رابط الصحة: /health على المنفذ {os.getenv("PORT", os.getenv("KEEP_ALIVE_PORT", "8080"))}')
    print('=' * 70)
    print('📌 في تليغرام:')
    print('   • الطلاب يستخدمون /start')
    print('   • الأدمن يستخدم /admin')
    print('   • الهيكل والملفات تدار من داخل البوت')
    print('   • UptimeRobot يقدر يعمل ping على /health')
    print('=' * 70 + '\n')

    logger.info('⏳ البوت ينتظر الرسائل...')

    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as exc:
            logger.error(f'❌ خطأ في التشغيل: {exc}')
            logger.info('🔄 إعادة المحاولة بعد 5 ثوانٍ...')
            time.sleep(5)
        else:
            logger.warning('⚠️ polling توقف بدون استثناء، ستتم إعادة التشغيل بعد 5 ثوانٍ')
            time.sleep(5)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info('🛑 تم إيقاف البوت')
        print('\n✅ تم الإيقاف بنجاح\n')
    except Exception as exc:
        logger.error(f'❌ خطأ حرج: {exc}')
        import traceback
        traceback.print_exc()
