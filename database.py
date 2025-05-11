# database.py
# 유저 상태, 연결 코드, 솔로모드 이용 기록 등을 저장하는 인메모리 데이터베이스

from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes

# 연결 코드 저장: 코드 → {'user_ids': [...], 'groups': [...], 'expires_at': datetime}
code_registry = {}

# 유저가 입력한 코드 등록 내역: user_id → [code1, code2, ...]
user_codes = {}

# 솔로모드 이용 기록: user_id → {'start': datetime, 'extend_count': 1, 'expire': datetime}
solo_mode_users = {}

# 소유자 인증 정보: 소유자 1명만 가능
owner_id = None

# 그룹 ID 등록
control_group_id = None
log_group_id = None
user_log_group_id = None

# 코드당 허용된 그룹 수
MAX_GROUPS_PER_CODE = 2

# 코드 생성 제한: user_id → 생성 횟수/월
code_creation_count = {}

# 소유자 인증
def set_owner(user_id):
    global owner_id
    owner_id = user_id

def is_owner(user_id):
    return owner_id == user_id

def get_owner():
    return owner_id

# 소유자 제어 그룹 등록
def set_control_group(chat_id):
    global control_group_id
    control_group_id = chat_id

def is_control_group(chat_id):
    return control_group_id == chat_id

def set_log_group(chat_id):
    global log_group_id
    log_group_id = chat_id

def is_log_group(chat_id):
    return log_group_id == chat_id

def set_user_log_group(chat_id):
    global user_log_group_id
    user_log_group_id = chat_id

def is_user_log_group(chat_id):
    return user_log_group_id == chat_id

# 코드 생성 제한 확인
def can_create_code(user_id):
    now = datetime.now()
    month_key = now.strftime("%Y-%m")
    key = f"{user_id}_{month_key}"
    return code_creation_count.get(key, 0) < 3

def register_code_creation(user_id):
    now = datetime.now()
    month_key = now.strftime("%Y-%m")
    key = f"{user_id}_{month_key}"
    code_creation_count[key] = code_creation_count.get(key, 0) + 1

# 코드 등록
def register_code(code, user_id, duration_days=3):
    expires = datetime.now() + timedelta(days=duration_days)
    code_registry[code] = {
        "user_ids": [user_id],
        "groups": [],
        "expires_at": expires
    }
    if user_id not in user_codes:
        user_codes[user_id] = []
    user_codes[user_id].append(code)

# 코드 유효성 확인
def is_code_valid(code):
    if code not in code_registry:
        return False
    return datetime.now() < code_registry[code]["expires_at"]

# 코드에 그룹 등록
def register_group_to_code(code, group_id):
    if code not in code_registry:
        return False
    if group_id in code_registry[code]["groups"]:
        return True
    if len(code_registry[code]["groups"]) >= MAX_GROUPS_PER_CODE:
        return False
    code_registry[code]["groups"].append(group_id)
    return True

# 솔로모드 활성화
def activate_solo_mode(user_id):
    if user_id not in solo_mode_users:
        solo_mode_users[user_id] = {
            "start": datetime.now(),
            "extend_count": 0,
            "expire": datetime.now() + timedelta(days=3)
        }

def can_extend_solo_mode(user_id):
    info = solo_mode_users.get(user_id)
    if not info:
        return False
    return info["extend_count"] < 2

def extend_solo_mode(user_id):
    if not can_extend_solo_mode(user_id):
        return False
    solo_mode_users[user_id]["extend_count"] += 1
    solo_mode_users[user_id]["expire"] += timedelta(days=3)
    return True

def is_solo_mode_active(user_id):
    info = solo_mode_users.get(user_id)
    if not info:
        return False
    return datetime.now() < info["expire"]

# ✅ 연결 해제 명령어용 함수 추가
async def disconnect_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ 연결이 해제되었습니다.")
