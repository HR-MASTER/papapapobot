# main.py

import os
import time
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv
import database
from translator import handle_translation

# ───────────────────────────────
# 환경 변수 및 로깅 설정
# ───────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")
OWNER_SECRET     = os.getenv("OWNER_SECRET")
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))
TUAPI_BASE_URL   = os.getenv("TUAPI_BASE_URL")
TUAPI_API_KEY    = os.getenv("TUAPI_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def init_bot_data(app):
    app.bot_data.setdefault("payment_invoice", {})
    # 문의 메시지 기본값 (4개국어)
    app.bot_data.setdefault("inquiry_msg", [
        "⏳ 기간 연장 문의 하기",
        "⏳ 请求续期",
        "⏳ ស្នើរសុំពន្យារពេល",
        "⏳ Yêu cầu gia hạn"
    ])
    # 사용자 메시지 로그 (timestamp, group_id, user_id, username, message)
    app.bot_data.setdefault("user_logs", [])
    # 코드 발급·사용·연장·삭제 로그
    # items: dict with keys (time, action, code, code_type, owner_id, user_id, group_id, user_name, days)
    app.bot_data.setdefault("code_logs", [])

def format_multilang(ko, zh, km, vi) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# ───────────────────────────────
# 소유자 인증 & 제어 그룹 설정
# ───────────────────────────────
OWNER_ID      = None
CONTROL_GROUP = None

def owner_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        gid = update.effective_chat.id
        if OWNER_ID is None or uid != OWNER_ID:
            return await update.message.reply_text("❌ 소유자 전용 명령입니다.")
        if CONTROL_GROUP is not None and gid != CONTROL_GROUP:
            return await update.message.reply_text("❌ 이 그룹에서만 사용할 수 있습니다.")
        return await func(update, ctx)
    return wrapper

async def auth_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    args = ctx.args
    if not args or args[0] != OWNER_SECRET:
        return await update.message.reply_text("❌ 인증에 실패했습니다.")
    OWNER_ID = update.effective_user.id
    await update.message.reply_text("✅ 소유자 인증 완료")

@owner_only
async def setcontrol_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global CONTROL_GROUP
    old = CONTROL_GROUP
    new = update.effective_chat.id
    CONTROL_GROUP = new
    # 이전 제어그룹 해제 안내
    if old and old != new:
        try:
            await ctx.bot.send_message(chat_id=old, text="❌ 이 그룹은 더 이상 제어 그룹이 아닙니다.")
        except:
            pass
    await update.message.reply_text("✅ 제어 그룹으로 지정되었습니다.")

@owner_only
async def setinquiry_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.partition(" ")[2]
    parts = text.split("|")
    if len(parts) != 4:
        return await update.message.reply_text(
            "❗ 사용법: /setinquiry <한국어>|<中文>|<ភាសាខ្មែរ>|<Tiếng Việt>"
        )
    ctx.bot_data["inquiry_msg"] = parts
    await update.message.reply_text("✅ 문의 메시지 설정 완료")

@owner_only
async def helpowner_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔐 소유자 전용 명령어\n"
        "/auth <코드>                         – 소유자 인증\n"
        "/setcontrolgroup                   – 제어 그룹 지정\n"
        "/setinquiry <ko>|<zh>|<km>|<vi>    – /paymentcheck 안내문 설정\n"
        "/helpowner                         – 소유자 도움말\n"
        "/listmaster                        – 연결된 그룹 목록\n"
        "/forcedisconnect <그룹ID>          – 강제 해제\n"
        "/generateownercode <코드> <일수>    – 소유자 코드 생성\n"
        "/removeowner                       – 소유자 권한 해제\n"
        "/getlogs <그룹ID>                  – 메시지 로그 조회\n"
        "/listcodelogs [코드]               – 코드 발급/사용/삭제 로그 조회\n"
        "/deletecode <코드>                 – 코드 삭제\n"
        "/extendissuedcode <코드> <일수>     – 코드 기한 연장\n"
    )
    await update.message.reply_text(text)

@owner_only
async def listmaster_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lines = []
    for gid, info in database._groups.items():
        days = int((info["expires"] - time.time()) // 86400)
        chat = await ctx.bot.get_chat(gid)
        name = getattr(chat, "title", None) \
            or f"{chat.first_name or ''} {chat.last_name or ''}".strip() \
            or chat.username or str(gid)
        lines.append(f"{gid} ({name}): code={info['code']} 남은{days}일")
    text = "🗂 연결된 그룹 목록\n" + ("\n".join(lines) if lines else "없음")
    await update.message.reply_text(text)

@owner_only
async def forcedisconnect_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /forcedisconnect <그룹ID>")
    database.disconnect_user(int(ctx.args[0]))
    await update.message.reply_text("✅ 강제 해제 완료")

@owner_only
async def generateownercode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 2 or not ctx.args[1].isdigit():
        return await update.message.reply_text("❗ 사용법: /generateownercode <코드> <일수>")
    code, days = ctx.args[0], int(ctx.args[1])
    database._codes[code] = {
        "owner": OWNER_ID,
        "expires": time.time() + days * 86400,
        "is_owner_code": True
    }
    # 로그 기록
    ctx.bot_data["code_logs"].append({
        "time": time.time(),
        "action": "issue_owner",
        "code": code,
        "code_type": "owner",
        "owner_id": OWNER_ID,
        "user_id": None,
        "group_id": None,
        "user_name": None,
        "days": days
    })
    await update.message.reply_text(f"✅ 소유자 코드 {code}({days}일) 발급 완료")

@owner_only
async def removeowner_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID, CONTROL_GROUP
    OWNER_ID = CONTROL_GROUP = None
    await update.message.reply_text("✅ 소유자 권한 해제")

@owner_only
async def getlogs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /getlogs <그룹ID>")
    gid = int(ctx.args[0])
    logs = ctx.bot_data["user_logs"]
    entries = [
        f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(t))} | {uid}({uname}): {msg}"
        for t, group, uid, uname, msg in logs if group == gid
    ][-20:]
    if not entries:
        return await update.message.reply_text("❗ 로그가 없습니다.")
    await update.message.reply_text("📝 최근 메시지 로그\n" + "\n".join(entries))

@owner_only
async def listcodelogs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logs = ctx.bot_data["code_logs"]
    code_filter = ctx.args[0] if ctx.args else None
    filtered = [
        log for log in logs
        if not code_filter or log["code"] == code_filter
    ]
    if not filtered:
        return await update.message.reply_text("❗ 로그 항목이 없습니다.")
    lines = []
    for log in filtered[-20:]:
        ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(log["time"]))
        act = log["action"]
        code = log["code"]
        days = log.get("days", "")
        lines.append(f"{ts} | {act} | {code} | {days}")
    await update.message.reply_text("🔖 코드 로그\n" + "\n".join(lines))

@owner_only
async def deletecode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or len(ctx.args) != 1:
        return await update.message.reply_text("❗ 사용법: /deletecode <코드>")
    code = ctx.args[0]
    if database.delete_code(code):
        ctx.bot_data["code_logs"].append({
            "time": time.time(),
            "action": "delete",
            "code": code,
            "code_type": None,
            "owner_id": OWNER_ID,
            "user_id": None,
            "group_id": None,
            "user_name": None,
            "days": None
        })
        await update.message.reply_text(f"✅ 코드 {code} 삭제 완료")
    else:
        await update.message.reply_text("❗ 해당 코드를 찾을 수 없습니다.")

@owner_only
async def extendissuedcode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 2 or not ctx.args[1].isdigit():
        return await update.message.reply_text("❗ 사용법: /extendissuedcode <코드> <일수>")
    code, days = ctx.args[0], int(ctx.args[1])
    if database.extend_code(code, days):
        ctx.bot_data["code_logs"].append({
            "time": time.time(),
            "action": "extend_issue",
            "code": code,
            "code_type": None,
            "owner_id": OWNER_ID,
            "user_id": None,
            "group_id": None,
            "user_name": None,
            "days": days
        })
        await update.message.reply_text(f"✅ 코드 {code} 기한 연장 완료 (+{days}일)")
    else:
        await update.message.reply_text("❗ 해당 코드를 찾을 수 없습니다.")

# ───────────────────────────────
# 사용자용 핸들러
# ───────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_multilang(
            "✅ 번역봇이 작동 중입니다. /help 입력",
            "✅ Translation bot is running. Type /help",
            "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
            "✅ Bot dịch đang hoạt động. Gõ /help"
        )
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "[한국어]\n"
        "/createcode   – 코드 생성 (무료3일)\n"
        "/registercode – 그룹에 코드 등록\n"
        "/disconnect   – 연결 해제\n"
        "/extendcode   – 코드 연장 3일 (1회)\n"
        "/remaining    – 남은 기간 확인\n"
        "/paymentcheck – 기간 연장 문의 하기\n\n"
        "[中文]\n"
        "/createcode   – 创建代码 (免费3天)\n"
        "/registercode – 群组注册代码\n"
        "/disconnect   – 断开连接\n"
        "/extendcode   – 延长代码3天 (1次)\n"
        "/remaining    – 查看剩余时间\n"
        "/paymentcheck – 请求续期\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode   – បង្កើតកូដ (ឥតគិតថ្លៃ3ថ្ងៃ)\n"
        "/registercode – ក្រុមចុះបញ្ជីកូដ\n"
        "/disconnect   – ផ្តាច់ការតភ្ជាប់\n"
        "/extendcode   – ពន្យារកូដ3ថ្ងៃ (1ដង)\n"
        "/remaining    – ពិនិត្យរយៈពេលនៅសល់\n"
        "/paymentcheck – ស្នើរសុំពន្យារពេល\n\n"
        "[Tiếng Việt]\n"
        "/createcode   – Tạo mã (miễn phí3ngày)\n"
        "/registercode – Nhóm đăng ký mã\n"
        "/disconnect   – Ngắt kết nối\n"
        "/extendcode   – Gia hạn mã3ngày (1 lần)\n"
        "/remaining    – Kiểm tra thời gian còn lại\n"
        "/paymentcheck – Yêu cầu gia hạn\n"
    )
    kb = [
        [InlineKeyboardButton("CreateCode",   callback_data="btn_create")],
        [InlineKeyboardButton("RegisterCode", callback_data="btn_register")],
        [InlineKeyboardButton("Disconnect",   callback_data="btn_disconnect")],
        [InlineKeyboardButton("ExtendCode",   callback_data="btn_extend")],
        [InlineKeyboardButton("Remaining",    callback_data="btn_remaining")],
        [InlineKeyboardButton("PaymentCheck", callback_data="btn_payment")],
    ]
    await update.message.reply_text(help_text, reply_markup=InlineKeyboardMarkup(kb))

async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cmd = q.data.split("_")[1]
    fake = Update(update.update_id, message=q.message, callback_query=q)
    mapping = {
        "create":    createcode,
        "register":  registercode,
        "disconnect":disconnect,
        "extend":    extendcode,
        "remaining": remaining,
        "payment":   paymentcheck
    }
    if cmd in mapping:
        return await mapping[cmd](fake, ctx)

async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    uname = update.effective_user.username or update.effective_user.full_name
    code  = database.register_code(uid, duration_days=3, max_free=1)
    if code is None:
        return await update.message.reply_text(
            format_multilang(
                "⚠️ 무료 코드 발급 한도(1회) 초과",
                "⚠️ Free limit reached (1)",
                "⚠️ លើសកំណត់ឥតគិតថ្លៃ(1ដង)",
                "⚠️ Hết lượt miễn phí (1 lần)"
            )
        )
    # 로그 기록
    ctx.bot_data["code_logs"].append({
        "time": time.time(),
        "action": "issue_user",
        "code": code,
        "code_type": "user",
        "owner_id": uid,
        "user_id": uid,
        "group_id": None,
        "user_name": uname,
        "days": 3
    })
    await update.message.reply_text(
        format_multilang(
            f"✅ 코드 생성: {code} (3일간 유효)",
            f"✅ Code created: {code} (3 days)",
            f"✅ បានបង្កើតកូដ: {code} (3ថ្ងៃ)",
            f"✅ Tạo mã: {code} (3 ngày)"
        )
    )

async def registercode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args; gid = update.effective_chat.id
    if not args:
        return await update.message.reply_text("/registercode [code]")
    code = args[0]
    if not database.register_group_to_code(code, gid, duration_days=3):
        return await update.message.reply_text(
            format_multilang(
                "❌ 코드 유효하지 않거나 그룹 초과",
                "❌ Invalid code or full",
                "❌ កូដមិនត្រឹមត្រូវ ឬក្រុមពេញ",
                "❌ Mã không hợp lệ hoặc đầy"
            )
        )
    rem = database.group_remaining_seconds(gid) // 86400
    uname = update.effective_user.username or update.effective_user.full_name
    # 로그 기록
    ctx.bot_data["code_logs"].append({
        "time": time.time(),
        "action": "use",
        "code": code,
        "code_type": None,
        "owner_id": None,
        "user_id": update.effective_user.id,
        "group_id": gid,
        "user_name": uname,
        "days": None
    })
    ctx.bot_data["user_logs"].append((
        time.time(), gid, update.effective_user.id, uname, f"/registercode {code}"
    ))
    await update.message.reply_text(
        format_multilang(
            f"✅ 등록 완료: {code} (남은 {rem}일)",
            f"✅ Registered: {code} ({rem}d left)",
            f"✅ ចុះបញ្ជីរ: {code} ({rem}ថ្ងៃសល់)",
            f"✅ Đã đăng ký: {code} (còn {rem} ngày)"
        )
    )

async def disconnect(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    database.disconnect_user(gid)
    await update.message.reply_text(
        format_multilang(
            "🔌 연결이 해제되었습니다.",
            "🔌 Disconnected.",
            "🔌 ផ្តាច់ការតភ្ជាប់រួចរាល់។",
            "🔌 Đã ngắt kết nối."
        )
    )

async def extendcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.extend_group(gid, duration_days=3, max_extends=1):
        rem = database.group_remaining_seconds(gid) // 86400
        await update.message.reply_text(
            format_multilang(
                f"🔁 코드 연장 완료. 남은 {rem}일",
                f"🔁 Extended: {rem} days",
                f"🔁 ពន្យារួច. {rem}ថ្ងៃសល់",
                f"🔁 Gia hạn. Còn {rem} ngày"
            )
        )
    else:
        await update.message.reply_text(
            format_multilang(
                "⚠️ 연장 한도(1회) 초과",
                "⚠️ Extension limit reached",
                "⚠️ លើសកំណត់ពន្យារ(1ដង)",
                "⚠️ Vượt giới hạn (1 lần)"
            )
        )

async def remaining(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    sec = database.group_remaining_seconds(gid)
    if sec <= 0:
        msg = format_multilang(
            "❗ 등록된 코드가 없습니다.",
            "❗ No code registered.",
            "❗ មិនមានកូដ។",
            "❗ Không có mã."
        )
    else:
        d, h, m = sec // 86400, (sec % 86400) // 3600, (sec % 3600) // 60
        msg = format_multilang(
            f"⏳ 남은: {d}일 {h}시간 {m}분",
            f"⏳ Remaining: {d}d {h}h {m}m",
            f"⏳ នៅសល់: {d}ថ្ងៃ {h}ម៉ោង {m}នាទី",
            f"⏳ Còn lại: {d}ngày {h}giờ {m}phút"
        )
    await update.message.reply_text(msg)

async def paymentcheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ko, zh, km, vi = ctx.bot_data["inquiry_msg"]
    await update.message.reply_text(format_multilang(ko, zh, km, vi))

async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.is_group_active(gid):
        uname = update.effective_user.username or update.effective_user.full_name
        ctx.bot_data["user_logs"].append((
            time.time(), gid,
            update.effective_user.id,
            uname,
            update.message.text
        ))
        await handle_translation(update, ctx)

if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 소유자용 핸들러
    app.add_handler(CommandHandler("auth",             auth_cmd))
    app.add_handler(CommandHandler("setcontrolgroup",  setcontrol_cmd))
    app.add_handler(CommandHandler("setinquiry",       setinquiry_cmd))
    app.add_handler(CommandHandler("helpowner",        helpowner_cmd))
    app.add_handler(CommandHandler("listmaster",       listmaster_cmd))
    app.add_handler(CommandHandler("forcedisconnect",  forcedisconnect_cmd))
    app.add_handler(CommandHandler("generateownercode",generateownercode_cmd))
    app.add_handler(CommandHandler("removeowner",      removeowner_cmd))
    app.add_handler(CommandHandler("getlogs",          getlogs_cmd))
    app.add_handler(CommandHandler("listcodelogs",     listcodelogs_cmd))
    app.add_handler(CommandHandler("deletecode",       deletecode_cmd))
    app.add_handler(CommandHandler("extendissuedcode", extendissuedcode_cmd))

    # 사용자용 핸들러
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("help",        help_cmd))
    app.add_handler(CallbackQueryHandler(button_cb))
    app.add_handler(CommandHandler("createcode",   createcode))
    app.add_handler(CommandHandler("registercode", registercode))
    app.add_handler(CommandHandler("disconnect",   disconnect))
    app.add_handler(CommandHandler("extendcode",   extendcode))
    app.add_handler(CommandHandler("remaining",    remaining))
    app.add_handler(CommandHandler("paymentcheck", paymentcheck))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    app.run_polling(drop_pending_updates=True)
