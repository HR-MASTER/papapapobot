# payment.py
# TRC-20 USDT 결제 확인 모듈 - Trongrid API 사용

import os
import time
import requests
from dotenv import load_dotenv
from telegram import Update

load_dotenv()

TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY")
RECEIVER_ADDRESS = os.getenv("TRC20_RECEIVER_ADDRESS")
TRONGRID_BASE_URL = "https://api.trongrid.io/v1/accounts"

# 유저 ID와 생성된 코드에 대해 임시 결제주소 & 유효시간 저장 (메모리 DB)
pending_payments = {}

# 사용자에게 결제 안내 메시지 전송
async def handle_payment_check(update: Update, context):
    user_id = update.effective_user.id
    args = context.args

    if len(args) != 2:
        await update.message.reply_text("❗ 사용법: /결제확인 [TX해시] [코드]")
        return

    tx_hash, code = args

    if check_usdt_payment(tx_hash):
        # 여기서 코드 등록 로직으로 연결 가능
        await update.message.reply_text("✅ 결제가 확인되었습니다. 코드가 활성화됩니다.")
        # database.register_paid_code(code, user_id)  # 추후 연결
    else:
        await update.message.reply_text("❌ 결제를 찾을 수 없습니다. TX 해시를 다시 확인해주세요.")

# TRC-20 결제 확인 함수 (Trongrid API)
def check_usdt_payment(tx_hash):
    try:
        url = f"https://api.trongrid.io/v1/transactions/{tx_hash}"
        headers = {
            "accept": "application/json",
            "TRON-PRO-API-KEY": TRONGRID_API_KEY
        }
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            return False
        data = res.json()["data"][0]
        if "contractData" not in data:
            return False
        contract = data["raw_data"]["contract"][0]["parameter"]["value"]

        # 주소 & 토큰 기준 검증
        if (
            contract.get("contract_address") or ""
        ).lower() == RECEIVER_ADDRESS.lower() and contract.get("amount") >= 30000000:
            return True
    except Exception as e:
        print("결제 확인 오류:", str(e))
    return False
