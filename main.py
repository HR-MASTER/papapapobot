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
BOT_TOKEN      = os.getenv("BOT_TOKEN")
OWNER_SECRET   = os.getenv("OWNER_SECRET")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def init_bot_data(app):
    app.bot_data.setdefault("inquiry_msg", [
        "⏳ 기간 연장 문의 하기",
        "⏳ 请求续期",
        "⏳ ស្នើរសុំពន្យារពេល",
        "⏳ Yêu cầu gia hạn"
    ])
    # (timestamp, chat_id, user_id, username, message)
    app.bot_data.setdefault("user_logs", [])
    app.bot_data.setdefault("code_logs", [])

def format_multilang(ko, zh, km, vi) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# ───────────────────────────────
# 소유자 인증 / 제어 그룹
# ───────────────────────────────
OWNER_ID      = None
CONTROL_GROUP = None

def owner_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid  = update.effective_user.id
        chat = update.effective_chat
        if OWNER_ID is None or uid != OWNER_ID:
            return await update.message.reply_text("❌ 소유자 전용 명령입니다.")
        # 개인(chat.type=="private")은 항상 허용
        if chat.type != "private" and CONTROL_GROUP is not None and chat.id != CONTROL_GROUP:
            return await update.message.reply_text("❌ 이 그룹에서만 사용할 수 있습니다.")
        return await func(update, ctx)
    return wrapper

# — 인증
async def auth_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global OWNER_ID
    if not ctx.args or ctx.args[0] != OWNER_SECRET:
        return await update.message.reply_text("❌ 인증에 실패했습니다.")
    OWNER_ID = update.effective_user.id
    await update.message.reply_text("✅ 소유자 인증 완료")

# — 제어 그룹 지정
@owner_only
async def setcontrol_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global CONTROL_GROUP
    prev = CONTROL_GROUP
    CONTROL_GROUP = update.effective_chat.id
    if prev and prev != CONTROL_GROUP:
        try:
            await ctx.bot.send_message(prev, "❌ 이 그룹은 더 이상 제어 그룹이 아닙니다.")
        except:
            pass
    await update.message.reply_text("✅ 제어 그룹으로 지정되었습니다.")

# — 연장 문의 메시지 설정
@owner_only
async def setinquiry_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.partition(" ")[2]
    parts = text.split("|")
    if len(parts) != 4:
        return await update.message.reply_text(
            "❗ 사용법: /setinquiry <한국어>|<中文>|<ភាសាខ្មែរ>|<Tiếng Việt>"
        )
    ctx.bot_data["inquiry_msg"] = parts
    await update.message.reply_text("✅ 연장 문의 메시지 설정 완료")

# — 소유자 도움말
@owner_only
async def helpowner_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "🔐 소유자 전용 명령어\n"
        "/auth <코드>                         – 소유자 인증\n"
        "/setcontrolgroup                   – 제어 그룹 지정\n"
        "/setinquiry <ko>|<zh>|<km>|<vi>    – 연장 문의 메시지 설정\n"
        "/helpowner                         – 소유자 도움말\n"
        "/listmaster                        – 연결된 그룹 목록\n"
        "/forcedisconnect <그룹ID>          – 강제 해제\n"
        "/generateownercode <코드> <일수>    – 소유자 코드 생성\n"
        "/deletecode <코드>                 – 코드 삭제\n"
        "/extendissuedcode <코드> <일수>     – 코드 기한 연장\n"
        "/listcodelogs [코드]               – 코드 로그 조회\n"
        "/getlogs <그룹ID>                  – 채팅 로그 조회\n"
        "/listparticipants <그룹ID>         – 그룹 참가자 목록 조회\n"
    )
    await update.message.reply_text(text)

# — 그룹 목록
@owner_only
async def listmaster_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    lines = []
    for gid, info in database._groups.items():
        days = int((info["expires"] - time.time()) // 86400)
        chat = await ctx.bot.get_chat(gid)
        name = getattr(chat, "title", None) or chat.username or str(gid)
        lines.append(f"{gid} ({name}): code={info['code']} 남은{days}일")
    await update.message.reply_text("🗂 연결된 그룹 목록\n" + ("\n".join(lines) if lines else "없음"))

# — 강제 해제
@owner_only
async def forcedisconnect_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /forcedisconnect <그룹ID>")
    database.disconnect_user(int(ctx.args[0]))
    await update.message.reply_text("✅ 강제 해제 완료")

# — 소유자 코드 생성
@owner_only
async def generateownercode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 2 or not ctx.args[1].isdigit():
        return await update.message.reply_text("❗ 사용법: /generateownercode <코드> <일수>")
    code, days = ctx.args[0], int(ctx.args[1])
    database.issue_owner_code(code, OWNER_ID, days)
    ctx.bot_data["code_logs"].append({
        "time": time.time(),
        "action": "issue_owner",
        "code": code,
        "days": days
    })
    await update.message.reply_text(f"✅ 소유자 코드 {code}({days}일) 발급 완료")

# — 코드 삭제
@owner_only
async def deletecode_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 1:
        return await update.message.reply_text("❗ 사용법: /deletecode <코드>")
    code = ctx.args[0]
    if database.delete_code(code):
        ctx.bot_data["code_logs"].append({
            "time": time.time(),
            "action": "delete",
            "code": code
        })
        await update.message.reply_text(f"✅ 코드 {code} 삭제 완료")
    else:
        await update.message.reply_text("❗ 해당 코드를 찾을 수 없습니다.")

# — 발급 코드 연장
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
            "days": days
        })
        await update.message.reply_text(f"✅ 코드 {code} 기한 연장 완료 (+{days}일)")
    else:
        await update.message.reply_text("❗ 해당 코드를 찾을 수 없습니다.")

# — 코드 로그 조회
@owner_only
async def listcodelogs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    logs = ctx.bot_data["code_logs"]
    code_filter = ctx.args[0] if ctx.args else None
    filtered = [l for l in logs if not code_filter or l["code"] == code_filter]
    if not filtered:
        return await update.message.reply_text("❗ 로그 항목이 없습니다.")
    lines = []
    for log in filtered[-20:]:
        ts = time.strftime('%Y-%m-%d %H:%M', time.localtime(log["time"]))
        lines.append(f"{ts} | {log['action']} | {log['code']} | {log.get('days','')}")
    await update.message.reply_text("🔖 코드 로그\n" + "\n".join(lines))

# — 채팅 로그 조회
@owner_only
async def getlogs_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 1 or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /getlogs <그룹ID>")
    gid = int(ctx.args[0])
    entries = [
        f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(t))} | {uid}({uname}): {msg}"
        for t, group, uid, uname, msg in ctx.bot_data["user_logs"]
        if group == gid
    ][-50:]
    if not entries:
        return await update.message.reply_text("❗ 로그가 없습니다.")
    await update.message.reply_text("📝 최근 메시지 로그\n" + "\n".join(entries))

# — 그룹 참가자 조회
@owner_only
async def listparticipants_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) != 1 or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ 사용법: /listparticipants <그룹ID>")
    gid = int(ctx.args[0])
    seen = {}
    for t, group, uid, uname, msg in ctx.bot_data["user_logs"]:
        if group == gid:
            seen[uid] = uname
    if not seen:
        return await update.message.reply_text("❗ 참가자가 없습니다.")
    lines = [f"{uid} ({uname})" for uid, uname in seen.items()]
    await update.message.reply_text("👥 그룹 참가자 목록\n" + "\n".join(lines))


# ───────────────────────────────
# 사용자용 핸들러
# ───────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(format_multilang(
        "✅ 번역봇이 작동 중입니다. /help 입력",
        "✅ Translation bot is running. Type /help",
        "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
        "✅ Bot dịch đang hoạt động. GÕ /help"
    ))

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
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
        "/registercode – ​ក្រុមចុះបញ្ជីកូដ\n"
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
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))

async def button_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    cmd = update.callback_query.data.split("_")[1]
    fake = Update(update.update_id,
                  message=update.callback_query.message,
                  callback_query=update.callback_query)
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
    if not code:
        return await update.message.reply_text("⚠️ 무료 코드 발급 한도(1회) 초과")
    ctx.bot_data["code_logs"].append({
        "time": time.time(), "action": "issue_user",
        "code": code, "owner_id": uid, "user_id": uid, "days": 3
    })
    await update.message.reply_text(f"✅ 코드 생성: {code} (3일간 유효)")

async def registercode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args; gid = update.effective_chat.id
    if not args:
        return await update.message.reply_text("/registercode [code]")
    code = args[0]
    if not database.register_group_to_code(code, gid):
        return await update.message.reply_text("❌ 코드 유효하지 않거나 그룹 초과")
    rem = database.group_remaining_seconds(gid) // 86400
    uname = update.effective_user.username or update.effective_user.full_name
    ctx.bot_data["code_logs"].append({
        "time": time.time(), "action": "use",
        "code": code, "user_id": uid, "group_id": gid
    })
    ctx.bot_data["user_logs"].append((
        time<|diff_marker|> truncated
