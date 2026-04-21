#!/usr/bin/env python3
"""
𝙼𝙴𝚁𝙾 𝙷𝙾𝚂𝚃 - بوت التحكم الكامل
طُوِّر بواسطة: 𝙉𝘼𝙎𝙎𝙄𝙈  𝙃𝙊𝙎𝙏 | @NASSIM_D5X
"""

import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)

# ========== إعدادات البوت ==========
BOT_TOKEN = "8676528994:AAFFbhvKNTAoElHYx0pzpT3TaLZxUE3b0js"
API_BASE_URL = os.environ.get("API_BASE_URL", "https://mero-host.onrender.com")

# إيدي الأدمن على تليجرام
ADMIN_TELEGRAM_IDS = [7092182498]

# معلومات المطور
DEVELOPER_INFO = "🛠 طُوِّر بواسطة: *𝙉𝘼𝙎𝙎𝙄𝙈  𝙃𝙊𝙎𝙏*\n📬 تواصل: @NASSIM_D5X"

# ========== حالات المحادثة ==========
(
    WAITING_FOR_API_KEY,
    WAITING_FOR_NEW_SERVER_NAME,
    WAITING_FOR_SERVER_TYPE,
    WAITING_FOR_DELETE_USERNAME,
) = range(4)


# ─────────────────────────────────────────────────
#  API Helper
# ─────────────────────────────────────────────────
def api_request(endpoint, method="GET", data=None, params=None, api_key=None):
    url = f"{API_BASE_URL}{endpoint}"
    try:
        if method == "GET":
            p = dict(params or {})
            if api_key:
                p["api_key"] = api_key
            resp = requests.get(url, params=p, timeout=30)
        else:
            d = dict(data or {})
            if api_key and "api_key" not in d:
                d["api_key"] = api_key
            resp = requests.post(url, json=d, timeout=30)
        return resp.json() if resp.ok else {"success": False, "message": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


def is_admin_tg(update: Update) -> bool:
    return update.effective_chat.id in ADMIN_TELEGRAM_IDS


# ─────────────────────────────────────────────────
#  القائمة الرئيسية
# ─────────────────────────────────────────────────
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=False):
    api_key = context.user_data.get("api_key")
    username = context.user_data.get("username", "")
    is_adm = is_admin_tg(update)

    keyboard = []

    if api_key:
        keyboard.append([
            InlineKeyboardButton("📁 سيرفراتي", callback_data="my_servers"),
            InlineKeyboardButton("➕ إنشاء سيرفر", callback_data="create_server"),
        ])
        keyboard.append([
            InlineKeyboardButton("🔑 تغيير API Key", callback_data="change_api"),
            InlineKeyboardButton("🚪 تسجيل خروج", callback_data="logout"),
        ])
    else:
        keyboard.append([InlineKeyboardButton("🔑 ربط API Key", callback_data="enter_api")])

    if is_adm:
        pending_count = 0
        result = api_request("/api/admin/pending", api_key=api_key)
        if result and result.get("success"):
            pending_count = len(result.get("requests", []))
        bell = f"🔔 إشعارات ({pending_count})" if pending_count > 0 else "🔕 إشعارات"
        keyboard.append([
            InlineKeyboardButton("👑 لوحة الإدارة", callback_data="admin_panel"),
            InlineKeyboardButton(bell, callback_data="admin_notifications"),
        ])

    keyboard.append([InlineKeyboardButton("💬 تواصل مع المطور @NASSIM_D5X", url="https://t.me/NASSIM_D5X")])

    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "      𝙉𝘼𝙎𝙎𝙄𝙈  𝙃𝙊𝙎𝙏 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    if username:
        text += f"👤 أهلاً، *{username}*!\n"
    text += "✅ متصل بالنظام\n" if api_key else "⚠️ يجب ربط API Key أولاً\n"
    text += f"\n{DEVELOPER_INFO}"

    markup = InlineKeyboardMarkup(keyboard)
    try:
        if edit and update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
        elif update.message:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)
        else:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
    except Exception:
        pass


# ─────────────────────────────────────────────────
#  عرض السيرفرات
# ─────────────────────────────────────────────────
async def show_servers_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    api_key = context.user_data.get("api_key")
    if not api_key:
        await query.edit_message_text("❌ يجب ربط API Key أولاً.")
        return

    result = api_request("/api/bot/servers", api_key=api_key)
    if not result or not result.get("success"):
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "❌ فشل جلب السيرفرات\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "تحقق من صحة API Key.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")]]),
        )
        return

    servers = result.get("servers", [])
    if not servers:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "📭 لا توجد سيرفرات\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "أنشئ سيرفرك الأول الآن!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ إنشاء سيرفر", callback_data="create_server")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
            ]),
        )
        return

    await query.edit_message_text(f"📋 لديك *{len(servers)}* سيرفر:", parse_mode="Markdown")

    for srv in servers:
        status_emoji = "🟢" if srv["status"] == "Running" else "⚫"
        srv_type = srv.get("type", "Python")
        type_icon = "🐍" if srv_type == "Python" else "🟨"

        text = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{status_emoji} *{srv['title']}*\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{type_icon} النوع: `{srv_type}`\n"
            f"📊 الحالة: `{srv['status']}`\n"
            f"🔌 المنفذ: `{srv['port']}`\n"
            f"⏱ وقت التشغيل: {srv['uptime']}"
        )
        folder = srv["folder"]
        keyboard = [
            [
                InlineKeyboardButton("▶️ تشغيل", callback_data=f"srv_start|{folder}"),
                InlineKeyboardButton("⏹ إيقاف", callback_data=f"srv_stop|{folder}"),
                InlineKeyboardButton("🔄 إعادة", callback_data=f"srv_restart|{folder}"),
            ],
            [
                InlineKeyboardButton("🖥 كونسول", callback_data=f"console|{folder}"),
                InlineKeyboardButton("⚠️ أخطاء", callback_data=f"errors|{folder}"),
                InlineKeyboardButton("🗑 حذف", callback_data=f"srv_delete|{folder}"),
            ],
            [InlineKeyboardButton("📦 تثبيت مكتبات تلقائياً", callback_data=f"install|{folder}")],
        ]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    await query.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 القائمة الرئيسية", callback_data="main_menu")]]),
    )


# ─────────────────────────────────────────────────
#  لوحة الإدارة
# ─────────────────────────────────────────────────
async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح لك بالدخول.")
        return

    api_key = context.user_data.get("api_key")
    result = api_request("/api/admin/users", api_key=api_key)
    users = result.get("users", []) if result and result.get("success") else []

    pending_result = api_request("/api/admin/pending", api_key=api_key)
    pending_count = len(pending_result.get("requests", [])) if pending_result and pending_result.get("success") else 0

    text = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  👑 لوحة إدارة 𝙼𝙴𝚁𝙾 𝙷𝙾𝚂𝚃\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 المستخدمين: *{len(users)}*\n"
        f"🔔 طلبات معلقة: *{pending_count}*\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
    )
    for u in users[:10]:
        text += f"• `{u['username']}` | {u.get('max_servers', 1)} سيرفر\n"
    if len(users) > 10:
        text += f"... و {len(users) - 10} آخرين\n"

    bell = f"🔔 طلبات ({pending_count})" if pending_count > 0 else "🔕 لا طلبات"
    keyboard = [
        [
            InlineKeyboardButton(bell, callback_data="admin_notifications"),
            InlineKeyboardButton("📊 إحصائيات", callback_data="admin_stats"),
        ],
        [InlineKeyboardButton("🗑 حذف مستخدم", callback_data="admin_delete_user")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")],
    ]
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))


# ─────────────────────────────────────────────────
#  إشعارات الطلبات المعلقة
# ─────────────────────────────────────────────────
async def show_admin_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح.")
        return

    api_key = context.user_data.get("api_key")
    result = api_request("/api/admin/pending", api_key=api_key)

    if not result or not result.get("success"):
        await query.edit_message_text("❌ فشل جلب الإشعارات.")
        return

    requests_list = result.get("requests", [])

    if not requests_list:
        await query.edit_message_text(
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🔕 لا توجد طلبات معلقة\n"
            "━━━━━━━━━━━━━━━━━━━━",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]),
        )
        return

    await query.edit_message_text(
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🔔 طلبات حسابات جديدة ({len(requests_list)})\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )
    for req in requests_list:
        text = (
            f"👤 المستخدم: `{req['username']}`\n"
            f"📅 التاريخ: {req.get('created_at', '')[:19]}"
        )
        keyboard = [[
            InlineKeyboardButton("✅ قبول", callback_data=f"approve|{req['username']}"),
            InlineKeyboardButton("❌ رفض", callback_data=f"reject|{req['username']}"),
        ]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    await query.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]),
    )


# ─────────────────────────────────────────────────
#  /start
# ─────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = context.user_data.get("api_key")
    if api_key:
        result = api_request("/api/bot/verify", method="POST", data={"api_key": api_key})
        if result and result.get("success"):
            context.user_data["username"] = result.get("username")
            await show_main_menu(update, context)
            return ConversationHandler.END
        context.user_data.clear()

    keyboard = [
        [InlineKeyboardButton("🔑 إدخال API Key", callback_data="enter_api")],
        [InlineKeyboardButton("💬 تواصل مع المطور @I_tt_6", url="https://t.me/I_tt_6")],
    ]
    await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "      𝙼𝙴𝚁𝙾 𝙷𝙾𝚂𝚃 🚀\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "للاشتراك والحصول على حساب:\n"
        "📬 تواصل مع المطور: @NASSIM_D5X\n\n"
        f"{DEVELOPER_INFO}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_FOR_API_KEY


async def handle_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = update.message.text.strip()
    result = api_request("/api/bot/verify", method="POST", data={"api_key": api_key})
    if not result or not result.get("success"):
        keyboard = [[InlineKeyboardButton("💬 تواصل مع المطور", url="https://t.me/NASSIM_D5X")]]
        await update.message.reply_text(
            "❌ *مفتاح API غير صالح!*\n\n"
            "تحقق من الكود وحاول مرة أخرى\n"
            "أو تواصل مع المطور: @NASSIM_D5X",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return WAITING_FOR_API_KEY

    context.user_data["api_key"] = api_key
    context.user_data["username"] = result.get("username")
    context.user_data["is_admin"] = result.get("is_admin", False)

    await update.message.reply_text(
        f"✅ *تم الربط بنجاح!*\n"
        f"👤 مرحباً *{result.get('username')}*!",
        parse_mode="Markdown",
    )
    await show_main_menu(update, context)
    return ConversationHandler.END


# ─────────────────────────────────────────────────
#  إنشاء سيرفر
# ─────────────────────────────────────────────────
async def receive_server_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["pending_server_name"] = name
    keyboard = [[
        InlineKeyboardButton("🐍 Python", callback_data="server_type_python"),
        InlineKeyboardButton("🟨 Node.js", callback_data="server_type_nodejs"),
    ]]
    await update.message.reply_text(
        f"📦 *اختر نوع السيرفر:*\n\nالاسم: `{name}`",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_FOR_SERVER_TYPE


async def receive_server_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    srv_type = "Python" if query.data == "server_type_python" else "Node.js"
    name = context.user_data.get("pending_server_name", "Server")

    result = api_request("/api/bot/create_server", method="POST", data={
        "api_key": context.user_data["api_key"],
        "name": name,
        "server_type": srv_type,
        "plan": "free",
        "storage": 100,
        "ram": 256,
        "cpu": 0.5,
    })

    type_icon = "🐍" if srv_type == "Python" else "🟨"
    if result and result.get("success"):
        await query.edit_message_text(
            f"✅ *تم إنشاء السيرفر بنجاح!*\n\n"
            f"📛 الاسم: `{name}`\n"
            f"{type_icon} النوع: `{srv_type}`\n\n"
            f"ارفع ملفاتك عبر الموقع الآن.",
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(
            f"❌ *فشل الإنشاء!*\n{result.get('message', 'خطأ غير معروف')}",
            parse_mode="Markdown",
        )

    await show_main_menu(update, context)
    return ConversationHandler.END


# ─────────────────────────────────────────────────
#  كونسول وأخطاء
# ─────────────────────────────────────────────────
async def show_console(update: Update, context: ContextTypes.DEFAULT_TYPE, folder: str):
    query = update.callback_query
    result = api_request("/api/bot/console", params={"folder": folder}, api_key=context.user_data.get("api_key"))
    if result and result.get("success"):
        logs = result.get("logs", "لا توجد مخرجات")
        if len(logs) > 3500:
            logs = "...\n" + logs[-3500:]
        keyboard = [[
            InlineKeyboardButton("🔄 تحديث", callback_data=f"console|{folder}"),
            InlineKeyboardButton("🔙 رجوع", callback_data="my_servers"),
        ]]
        await query.edit_message_text(
            f"🖥 *كونسول السيرفر*\n```\n{logs}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.edit_message_text("❌ فشل جلب الكونسول")


async def show_errors(update: Update, context: ContextTypes.DEFAULT_TYPE, folder: str):
    query = update.callback_query
    result = api_request("/api/bot/errors", params={"folder": folder}, api_key=context.user_data.get("api_key"))
    if result and result.get("success"):
        errors = result.get("errors", "✅ لا توجد أخطاء")
        if len(errors) > 3500:
            errors = "...\n" + errors[-3500:]
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="my_servers")]]
        await query.edit_message_text(
            f"⚠️ *سجل الأخطاء*\n```\n{errors}\n```",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    else:
        await query.edit_message_text("❌ فشل جلب سجل الأخطاء")


# ─────────────────────────────────────────────────
#  إدارة المستخدمين (أدمن)
# ─────────────────────────────────────────────────
async def admin_delete_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin_tg(update):
        await query.edit_message_text("❌ غير مصرح.")
        return ConversationHandler.END
    await query.edit_message_text("📝 أرسل اسم المستخدم الذي تريد حذفه:")
    return WAITING_FOR_DELETE_USERNAME


async def admin_delete_user_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip()
    result = api_request("/api/admin/delete-user", method="POST", data={
        "api_key": context.user_data.get("api_key"),
        "username": username,
    })
    if result and result.get("success"):
        await update.message.reply_text(f"✅ تم حذف المستخدم `{username}`", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ فشل: {result.get('message', 'خطأ')}")
    await show_main_menu(update, context)
    return ConversationHandler.END


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    metrics = api_request("/api/system/metrics")
    cpu = metrics.get("cpu", "?") if metrics else "?"
    ram = metrics.get("memory", "?") if metrics else "?"
    disk = metrics.get("disk", "?") if metrics else "?"
    await query.edit_message_text(
        "━━━━━━━━━━━━━━━━━━━━\n"
        "  📊 إحصائيات النظام\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥 CPU:  *{cpu}%*\n"
        f"💾 RAM:  *{ram}%*\n"
        f"💿 Disk: *{disk}%*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_panel")]]),
    )


# ─────────────────────────────────────────────────
#  معالج الأزرار الرئيسي
# ─────────────────────────────────────────────────
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    # أزرار بدون "|"
    if data == "main_menu":
        await show_main_menu(update, context, edit=True)
    elif data == "my_servers":
        await show_servers_list(update, context)
    elif data in ("enter_api", "change_api"):
        context.user_data.pop("api_key", None)
        await query.edit_message_text(
            "🔑 *أدخل API Key الخاص بك:*\n\n"
            "يمكنك الحصول عليه من لوحة التحكم في الموقع.",
            parse_mode="Markdown",
        )
        return WAITING_FOR_API_KEY
    elif data == "logout":
        context.user_data.clear()
        await query.edit_message_text("🚪 تم تسجيل الخروج.\nاستخدم /start للدخول مجدداً.")
    elif data == "create_server":
        await query.edit_message_text(
            "➕ *إنشاء سيرفر جديد*\n\n📝 أرسل اسم السيرفر:",
            parse_mode="Markdown",
        )
        return WAITING_FOR_NEW_SERVER_NAME
    elif data == "admin_panel":
        await show_admin_panel(update, context)
    elif data == "admin_notifications":
        await show_admin_notifications(update, context)
    elif data == "admin_delete_user":
        return await admin_delete_user_start(update, context)
    elif data == "admin_stats":
        await admin_stats(update, context)

    # أزرار مع "|" → cmd|value
    elif "|" in data:
        cmd, value = data.split("|", 1)
        api_key = context.user_data.get("api_key")

        if cmd in ("srv_start", "srv_stop", "srv_restart", "srv_delete"):
            action = cmd.replace("srv_", "")
            result = api_request("/api/bot/server/action", method="POST", data={
                "api_key": api_key, "folder": value, "action": action,
            })
            if result and result.get("success"):
                await query.answer(result.get("message", "✅ تم")[:200], show_alert=True)
            else:
                await query.answer(f"❌ {result.get('message', 'فشل') if result else 'خطأ'}"[:200], show_alert=True)
            await show_servers_list(update, context)

        elif cmd == "console":
            await show_console(update, context, value)

        elif cmd == "errors":
            await show_errors(update, context, value)

        elif cmd == "install":
            result = api_request("/api/bot/install", method="POST", data={
                "api_key": api_key, "folder": value,
            })
            msg = result.get("message", "✅ جاري التثبيت") if result and result.get("success") else f"❌ {result.get('message','فشل') if result else 'خطأ'}"
            await query.edit_message_text(
                f"📦 *تثبيت المكتبات*\n\n{msg}\n\nتابع الكونسول للتفاصيل.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🖥 كونسول", callback_data=f"console|{value}"),
                    InlineKeyboardButton("🔙 رجوع", callback_data="my_servers"),
                ]]),
            )

        elif cmd == "approve":
            result = api_request("/api/admin/approve", method="POST", data={
                "api_key": api_key, "username": value,
            })
            msg = f"✅ تم قبول حساب {value}" if result and result.get("success") else "❌ فشل القبول"
            await query.answer(msg, show_alert=True)
            await show_admin_notifications(update, context)

        elif cmd == "reject":
            result = api_request("/api/admin/reject", method="POST", data={
                "api_key": api_key, "username": value,
            })
            msg = f"🚫 تم رفض طلب {value}" if result and result.get("success") else "❌ فشل الرفض"
            await query.answer(msg, show_alert=True)
            await show_admin_notifications(update, context)

    return ConversationHandler.END


# ─────────────────────────────────────────────────
#  تشغيل البوت
# ─────────────────────────────────────────────────
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(button_callback),
        ],
        states={
            WAITING_FOR_API_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_api_key)
            ],
            WAITING_FOR_NEW_SERVER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_server_name)
            ],
            WAITING_FOR_SERVER_TYPE: [
                CallbackQueryHandler(receive_server_type, pattern="^server_type_")
            ],
            WAITING_FOR_DELETE_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_delete_user_confirm)
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        per_user=True,
        per_chat=True,
    )

    application.add_handler(conv)
    print("🚀 𝙉𝘼𝙎𝙎𝙄𝙈  𝙃𝙊𝙎𝙏 Bot يعمل...")
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
