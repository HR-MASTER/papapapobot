# database.py

import time
import secrets

# 1) 코드(소유자) 저장소
_codes: dict[str, dict] = {}

# 2) 그룹 등록 저장소
# group_id -> {
#   code, expires, extend_count,
#   last_payment_check (ms since epoch)
# }
_groups: dict[int, dict] = {}

def generate_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

def register_code(owner_id: int, duration_days: int = 3) -> str:
    code = generate_code()
    expires = int(time.time()) + duration_days * 86400
    _codes[code] = {"owner": owner_id, "expires": expires}
    return code

def is_code_valid(code: str) -> bool:
    info = _codes.get(code)
    return bool(info and info["expires"] >= time.time())

def code_remaining_seconds(code: str) -> int:
    info = _codes.get(code)
    if not info: return 0
    return max(0, int(info["expires"] - time.time()))

def register_group_to_code(code: str, group_id: int, duration_days: int = 3) -> bool:
    if not is_code_valid(code) or group_id in _groups:
        return False
    now = time.time()
    _groups[group_id] = {
        "code": code,
        "expires": now + duration_days * 86400,
        "extend_count": 0,
        "last_payment_check": int(now * 1000)
    }
    return True

def is_group_active(group_id: int) -> bool:
    info = _groups.get(group_id)
    return bool(info and info["expires"] >= time.time())

def group_remaining_seconds(group_id: int) -> int:
    info = _groups.get(group_id)
    if not info: return 0
    return max(0, int(info["expires"] - time.time()))

def extend_group(group_id: int, duration_days: int = 30, max_extends: int = 2) -> bool:
    info = _groups.get(group_id)
    if not info or info["extend_count"] >= max_extends:
        return False
    info["expires"] += duration_days * 86400
    info["extend_count"] += 1
    return True

def update_last_payment_check(group_id: int, timestamp_ms: int):
    info = _groups.get(group_id)
    if info:
        info["last_payment_check"] = timestamp_ms

def get_last_payment_check(group_id: int) -> int:
    return _groups.get(group_id, {}).get("last_payment_check", 0)

def disconnect_user(update, context) -> None:
    gid = update.effective_chat.id
    _groups.pop(gid, None)
    context.bot_data.get("is_group_registered", {}).pop(gid, None)
    update.message.reply_text("🔌 연결이 해제되었습니다.")
