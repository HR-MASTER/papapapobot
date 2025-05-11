# main.py

import os
import time
import logging
import secrets
import requests
from typing import Tuple
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv
from translator import handle_translation
import database

# ───────────────────────────────
# 소유자 인증 및 명령 그룹 관리
# ───────────────────────────────
OWNER_ID: int | None = None
CONTROL_GROUP_ID: int | None = None
LOG_GROUP_ID: int | None = None
USER_LOG_GROUP_ID: int | None = None

def owner_only(func):
    async def wrapper(update, ctx, *args, **kwargs):
        global OWNER_ID, CONTROL_GROUP_ID
        uid = update.effective_user.id
        gid = update.effective_chat.id
        if OWNER_ID is None or uid != OWNER_ID:
            return await update.message.reply_text("❌ 소유자가 아닙니다.")
        if CONTROL_GROUP_ID is None or gid != CONTROL_GROUP_ID:
            return await update.message.reply_text("❌ 이 그룹에서만 사용할 수 있습니다.")
        return await func(update, ctx, *args, **kwargs)
    return wrapper

async def auth_cmd(update, ctx):
    global OWNER_ID, CONTROL_GROUP_ID, LOG_GROUP_ID, USER_LOG_GROUP_ID
    args = ctx.args
    if not args or args[0] != OWNER_SECRET:
        return await update.message.reply_text("❌ 인증 실패")
    OWNER_ID = update.effective_user.id
    CONTROL_GROUP_ID = LOG_GROUP_ID = USER_LOG_GROUP_ID = None
    await update.message.reply_text("✅ 소유자 인증 완료")

@owner_only
async def set_control_group(update, ctx):
    global CONTROL_GROUP_ID
    CONTROL_GROUP_ID = update.effective_chat.id
    await update.message.reply_text("✅ 소유자 명령 그룹으로 등록되었습니다.")

@owner_only
async def set_log_group(update, ctx):
    global LOG_GROUP_ID
    LOG_GROUP_ID = update.effective_chat.id
    await update.message.reply_text("✅ 로그 전송용 그룹으로 등록되었습니다.")

@owner_only
async def set_user_log_group(update, ctx):
    global USER_LOG_GROUP_ID
    USER_LOG_GROUP_ID = update.effective_chat.id
    await update.message.reply_text("✅ 사용자 메시지 기록용 그룹으로 등록되었습니다.")

@owner_only
async def list_master(update, ctx):
    text = ["🗂 연결된 그룹 목록:"]
    for gid, info in database._groups.items():
        exp = int(info["expires"] - time.time())//86400
        text.append(f"- {gid}: 코드={info['code']}, 남은일수={exp}일")
    await update.message.reply_text("\n".join(text))

@owner_only
async def forced_disconnect(update, ctx):
    if not ctx.args or not ctx.args[0].isdigit():
        return await update.message.reply_text("❗ /forcedisconnect <group_id>")
    target = int(ctx.args[0])
    database.disconnect_user(target)
    await update.message.reply_text(f"✅ 그룹 {target} 연결을 해제했습니다.")

@owner_only
async def generate_owner_code(update, ctx):
    if len(ctx.args) != 2 or not ctx.args[1].isdigit():
        return await update.message.reply_text("❗ /generateownercode <code> <days>")
    code, days = ctx.args[0], int(ctx.args[1])
    database._codes[code] = {
        "owner": OWNER_ID,
        "expires": int(time.time()) + days*86400
    }
    await update.message.reply_text(f"✅ 소유자 코드 {code}({days}일) 발급 완료")

@owner_only
async def remove_owner(update, ctx):
    global OWNER_ID, CONTROL_GROUP_ID, LOG_GROUP_ID, USER_LOG_GROUP_ID
    OWNER_ID = CONTROL_GROUP_ID = LOG_GROUP_ID = USER_LOG_GROUP_ID = None
    await update.message.reply_text("✅ 소유자 권한이 해제되었습니다.")

# ───────────────────────────────
# 환경 변수 및 로깅 설정
# ───────────────────────────────
load_dotenv()
BOT_TOKEN        = os.getenv("BOT_TOKEN")
GOOGLE_API_KEY   = os.getenv("GOOGLE_API_KEY")
OWNER_SECRET     = os.getenv("OWNER_SECRET")
PLAN_USD         = float(os.getenv("PLAN_USD", "30"))
TUAPI_BASE_URL   = os.getenv("TUAPI_BASE_URL")
TUAPI_API_KEY    = os.getenv("TUAPI_API_KEY")
TUAPI_API_SECRET = os.getenv("TUAPI_API_SECRET")

logging.basicConfig(level=logging.INFO)

def init_bot_data(app):
    app.bot_data.setdefault("payment_invoice", {})

def format_multilang(ko: str, zh: str, km: str, vi: str) -> str:
    return (
        f"[한국어]\n{ko}\n\n"
        f"[中文]\n{zh}\n\n"
        f"[ភាសាខ្មែរ]\n{km}\n\n"
        f"[Tiếng Việt]\n{vi}"
    )

# ───────────────────────────────
# Tuapi 연동 함수
# ───────────────────────────────
def generate_one_time_address_tuapi(gid: int) -> Tuple[str, str]:
    url = f"{TUAPI_BASE_URL}/v1/trc20/address"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    order_id = f"{gid}-{int(time.time())}"
    res = requests.post(url, json={"orderId": order_id}, headers=headers, timeout=10).json()
    if res.get("code") != 0:
        raise RuntimeError("TuAPI 주소 생성 실패")
    return res["data"]["address"], res["data"]["orderId"]

def check_tuapi_deposit(order_id: str) -> float:
    url = f"{TUAPI_BASE_URL}/v1/trc20/transaction"
    headers = {"Authorization": f"Bearer {TUAPI_API_KEY}"}
    resp = requests.get(url, params={"orderId": order_id}, headers=headers, timeout=10).json()
    if resp.get("code") != 0:
        raise RuntimeError("TuAPI 거래 조회 실패")
    return sum(tx["value"] for tx in resp["data"]) / 1e6

# ───────────────────────────────
# Command Handlers
# ───────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        format_multilang(
            "✅ 번역봇이 작동 중입니다. /help 입력",
            "✅ 翻译机器人正在运行。请输入 /help",
            "✅ បុតនៃការបកប្រែកំពុងដំណើរការ។ វាយ /help",
            "✅ Bot dịch đang hoạt động. Gõ /help"
        )
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "📌 Help – 다국어 안내 [한국어], [English], [中文], [ភាសាខ្មែរ], [Tiếng Việt]\n\n"
        "[한국어]\n"
        "/createcode – 3일 무료 코드 생성\n"
        "/registercode [코드] – 그룹에 코드 등록\n"
        "/disconnect – 연결 해제\n"
        "/solomode – 솔로 모드 (3일)\n"
        "/extendcode – 코드 3일 연장 (최대 2회)\n"
        "/remaining – 남은 기간 확인\n"
        "/paymentcheck – 결제 확인 및 연장/주소 발급\n\n"
        "[English]\n"
        "/createcode – Create 3-day free code\n"
        "/registercode [code] – Register code in group\n"
        "/disconnect – Disconnect\n"
        "/solomode – Solo mode (3 days)\n"
        "/extendcode – Extend code by 3 days (max 2)\n"
        "/remaining – Check remaining time\n"
        "/paymentcheck – Check payment / Extend or get address\n\n"
        "[中文]\n"
        "/createcode – 生成 3 天免费代码\n"
        "/registercode [代码] – 在群组注册代码\n"
        "/disconnect – 断开连接\n"
        "/solomode – 独享模式（3 天）\n"
        "/extendcode – 延长代码 3 天（最多 2 次）\n"
        "/remaining – 查询剩余时间\n"
        "/paymentcheck – 检查支付 / 延长或获取地址\n\n"
        "[ភាសាខ្មែរ]\n"
        "/createcode – បង្កើតកូដ 3 ថ្ងៃឥតគិតថ្លៃ\n"
        "/registercode [កូដ] – ចុះបញ្ជីកូដក្នុងក្រុម\n"
        "/disconnect – ផ្អាកការតភ្ជាប់\n"
        "/solomode – ម៉ូដផ្ទាល់ខ្លួន (3 ថ្ងៃ)\n"
        "/extendcode – ពន្យារកូដ 3 ថ្ងៃ (2 ដងអតិបര��ា)\n"
        "/remaining – ពិនិត្យមើលពេលនៅសល់\n"
        "/paymentcheck – ពិនិត្យការទូទាត់ / ពន្យារឬទទួលអាសយដ្ឋាន\n\n"
        "[Tiếng Việt]\n"
        "/createcode – Tạo mã miễn phí 3 ngày\n"
        "/registercode [mា...]"
    )
    await update.message.reply_text(text)

async def createcode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    code = database.register_code(uid, duration_days=3)
    if code is None:
        return await update.message.reply_text(
            format_multilang(
                "⚠️ 무료 코드 발급 한도(2회) 초과",
                "⚠️ 超过免费代码次数(2次)",
                "⚠️ លើសកំណត់(2ដង)",
                "⚠️ Vượt giới hạn (2 lần)"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 코드 생성: {code} (3일간 유효)",
            f"✅ 已创建代码: {code} (3天有效)",
            f"✅ បានបង្កើតកូដ: {code} (3ថ្ងៃ)",
            f"✅ Tạo mã: {code} (3ngày)"
        )
    )

async def registercode(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    gid = update.effective_chat.id
    if not args or len(args[0]) != 6:
        return await update.message.reply_text("❗ /registercode [6자리 코드]")
    code = args[0]
    if not database.register_group_to_code(code, gid, duration_days=3):
        return await update.message.reply_text(
            format_multilang(
                "❌ 코드 유효하지 않거나 이미 등록됨",
                "❌ 代码无效或已注册",
                "❌ កូដមិនមានសុពលភាព ឬបានចុះបញ្ជីរួច",
                "❌ Mã không hợp lệ hoặc đã đăng ký"
            )
        )
    await update.message.reply_text(
        format_multilang(
            f"✅ 그룹 등록 완료: {code} (3일간)",
            f"✅ 群组注册完成: {code} (3天有效)",
            f"✅ ក្រុមបានចុះបញ្ជី: {code} (3ថ្ងៃ)",
            f"✅ Nhóm đã đăng ký: {code} (3 ngày)"
        )
    )
