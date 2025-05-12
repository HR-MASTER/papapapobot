# main.py

import os
import time
import logging
import requests
from typing import Tuple
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
    app.bot_data.setdefault("user_logs", [])

def format_multilang(ko, zh, km, vi) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# ───────────────────────────────
# TUAPI 연동 (기존 /paymentcheck 로직 남아있지만
#                지금은 사용되지 않습니다)
# ───────────────────────────────
def generate_address(gid: int) -> Tuple[str, str]:
    url = f"{TUAPI_BASE_URL}/v1/trc20/address"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    order_id = f"{gid}-{int(time.time())}"
    res = requests.post(url, json={"orderId": order_id}, headers=headers, timeout=10).json()
    if res.get("code") != 0 or "data" not in res:
        raise RuntimeError("주소 생성 실패")
    return res["data"]["address"], res["data"]["orderId"]

def check_deposit(order_id: str) -> float:
    url = f"{TUAPI_BASE_URL}/v1/trc20/transaction"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    resp = requests.get(url, params={"orderId": order_id}, headers=headers, timeout=10).json()
    if resp.get("code") != 0 or "data" not in resp:
        raise RuntimeError("거래 조회 실패")
    return sum(tx["value"] for tx in resp["data"]) / 1e6

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
    CONTROL_GROUP = update.effective_chat.id
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
        "/auth <코드>               – 소유자 인증\n"
        "/setcontrolgroup           – 제어 그룹 지정\n"
        "/setinquiry <ko>|<zh>|<km>|<vi> – /paymentcheck 안내문 설정\n"
        "/helpowner                 – 소유자 도움말\n"
        "/listmaster                – 연결된 그룹 목록\n"
        "/forcedisconnect <ID>      – 강제 해제\n"
        "/generateownercode <코드> <일수> – 소유자 코드 생성\n"
        "/removeowner               – 소유자 권한 해제\n"
        "/getlogs <그룹ID>          – 사용자 메시지 로그 조회"
    )
    await update.message.reply_text(text)

@owner_only
async def listmaster_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lines = []
    for gid, info in database._groups.items():
        days = int((info["expires"] - time.time())//86400)
        conn = info.get("connected", False)
        lines.append(f"{gid}: code={info['code']} days_left={days} connected={conn}")
    text = "🗂 연결된 그룹 목록\n" + ("\n".join(lines) if lines else "없음")
    await update.message.reply_text(text)

@owner_only
async def forcedisconnect_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /forcedisconnect <group_id>")
    database.disconnect_user(int(ctx.args[0]))
    await update.message.reply_text("✅ 강제 해제 완료")

@owner_only
async def generateownercode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args)!=2 or not ctx.args[1].isdigit():
        return await update.message.reply_text("❗ 사용법: /generateownercode <code> <days>")
    code, days = ctx.args[0], int(ctx.args[1])
    database._codes[code] = {"owner": OWNER_ID, "expires": time.time()+days*86400}
    await update.message.reply_text(f"✅ 소유자 코드 {code}({days}일) 발급")

@owner_only
async def removeowner_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID, CONTROL_GROUP
    OWNER_ID = CONTROL_GROUP = None
    await update.message.reply_text("✅ 소유자 권한 해제")

@owner_only
async def getlogs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /getlogs <group_id>")
    gid = int(ctx.args[0])
    logs = ctx.bot_data.get("user_logs", [])
    entries = [f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(t))} | {uid}: {msg}"
               for t, group, uid, msg in logs if group == gid][-20:]
    if not entries:
        return await update.message.reply_text("❗ 로그가 없습니다.")
    await update.message.reply_text("📝 최근 메시지 로그\n" + "\n".join(entries))

# ───────────────────────────────
# /start
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

# ───────────────────────────────
# /help (사용자용)
# ───────────────────────────────
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
        "/disconnect   – ផ្អាកការតភ្ជាប់\n"
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

# ───────────────────────────────
# 버튼 콜백
# ───────────────────────────────
async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer()
    cmd = q.data.split("_")[1]
    fake = Update(update.update_id, message=q.message, callback_query=q)
    mapping = {
        "create":   createcode,
        "register": registercode,
        "disconnect":disconnect,
        "extend":   extendcode,
        "remaining":remaining,
        "payment":  paymentcheck
    }
    if cmd in mapping:
        return await mapping[cmd](fake, ctx)

# ───────────────────────────────
# /createcode
# ───────────────────────────────
async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    code = database.register_code(uid, duration_days=3, max_free=1)
    if code is None:
        return await update.message.reply_text(
            format_multilang(
                "⚠️ 무료 코드 발급 한도(1회) 초과",
                "⚠️ Free limit reached (1)",
                "⚠️ លើសកំណត់ឥតគិតថ្លៃ(1ដង)",
                "⚠️ Hết lượt miễn phí (1 lần)"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 코드 생성: {code} (3일간 유효)",
            f"✅ Code created: {code} (3 days)",
            f"✅ បានបង្កើតកូដ: {code} (3ថ្ងៃ)",
            f"✅ Tạo mã: {code} (3 ngày)"
        )
    )

# ───────────────────────────────
# /registercode
# ───────────────────────────────
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
    await update.message.reply_text(
        format_multilang(
            f"✅ 등록 완료: {code} (남은 {rem}일)",
            f"✅ Registered: {code} ({rem}d left)",
            f"✅ ចុះបញ្ជីរ: {code} ({rem}ថ្ងៃសល់)",
            f"✅ Đã đăng ký: {code} (còn {rem} ngày)"
        )
    )

# ───────────────────────────────
# /disconnect
# ───────────────────────────────
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

# ───────────────────────────────
# /extendcode
# ───────────────────────────────
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

# ───────────────────────────────
# /remaining
# ───────────────────────────────
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

# ───────────────────────────────
# /paymentcheck → 기간 연장 문의하기
# ───────────────────────────────
async def paymentcheck(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    # 항상 multi-lang 문의 메시지 전송
    ko, zh, km, vi = ctx.bot_data["inquiry_msg"]
    await update.message.reply_text(format_multilang(ko, zh, km, vi))

# ───────────────────────────────
# 메시지 핸들링 (번역)
# ───────────────────────────────
async def message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    gid = update.effective_chat.id
    if database.is_group_active(gid):
        # 사용자 메시지 로그 저장
        ctx.bot_data["user_logs"].append((
            time.time(), gid,
            update.effective_user.id,
            update.message.text
        ))
        await handle_translation(update, ctx)

# ───────────────────────────────
# 봇 구동
# ───────────────────────────────
if __name__ == "__main__":
    logging.info("✅ 번역봇 시작")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    init_bot_data(app)

    # 소유자용
    app.add_handler(CommandHandler("auth",            auth_cmd))
    app.add_handler(CommandHandler("setcontrolgroup", setcontrol_cmd))
    app.add_handler(CommandHandler("setinquiry",      setinquiry_cmd))
    app.add_handler(CommandHandler("helpowner",       helpowner_cmd))
    app.add_handler(CommandHandler("listmaster",      listmaster_cmd))
    app.add_handler(CommandHandler("forcedisconnect", forcedisconnect_cmd))
    app.add_handler(CommandHandler("generateownercode",generateownercode_cmd))
    app.add_handler(CommandHandler("removeowner",     removeowner_cmd))
    app.add_handler(CommandHandler("getlogs",         getlogs_cmd))

    # 사용자용
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
