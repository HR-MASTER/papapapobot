# database.py

import time
import secrets

# ───────────────────────────────
# 1) 사용자 코드(소유자) 관리 (_codes)
# ───────────────────────────────
# code -> { owner, expires }
_codes: dict[str, dict] = {}

def register_code(owner_id: int, duration_days: int = 3) -> str | None:
    """
    새 코드 발급(무료) – 한 owner 당 최대 2회.
    허용량 초과 시 None 반환.
    """
    used = sum(1 for info in _codes.values() if info["owner"] == owner_id)
    if used >= 2:
        return None
    code = f"{secrets.randbelow(900000) + 100000}"
    expires = int(time.time()) + duration_days * 86400
    _codes[code] = {"owner": owner_id, "expires": expires}
    return code

def is_code_valid(code: str) -> bool:
    info = _codes.get(code)
    return bool(info and info["expires"] >= time.time())

def code_remaining_seconds(code: str) -> int:
    info = _codes.get(code)
    if not info:
        return 0
    return max(0, int(info["expires"] - time.time()))

# ───────────────────────────────
# 2) 그룹 연결 관리 (_groups)
# ───────────────────────────────
# group_id -> { code, expires, extend_count, last_payment_check }
_groups: dict[int, dict] = {}

def register_group_to_code(code: str, group_id: int, duration_days: int = 3) -> bool:
    if not is_code_valid(code) or group_id in _groups:
        return False
    now = time.time()
    _groups[group_id] = {
        "code": code,
        "expires": now + duration_days * 86400,
        "extend_count": 0,
        "last_payment_check": 0
    }
    return True

def is_group_active(group_id: int) -> bool:
    info = _groups.get(group_id)
    return bool(info and info["expires"] >= time.time())

def group_remaining_seconds(group_id: int) -> int:
    info = _groups.get(group_id)
    if not info:
        return 0
    return max(0, int(info["expires"] - time.time()))

def extend_group(group_id: int, duration_days: int = 3, max_extends: int = 2) -> bool:
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

def disconnect_user(group_id: int) -> None:
    _groups.pop(group_id, None)

# ───────────────────────────────
# 3) 솔로모드 관리 (_solo)
# ───────────────────────────────
# user_id -> { expires, extend_count }
_solo: dict[int, dict] = {}

def activate_solo_mode(user_id: int, duration_days: int = 3):
    now = int(time.time())
    _solo[user_id] = {
        "expires": now + duration_days * 86400,
        "extend_count": 0
    }

def is_solo_mode_active(user_id: int) -> bool:
    info = _solo.get(user_id)
    return bool(info and info["expires"] >= int(time.time()))

def can_extend_solo_mode(user_id: int, max_extends: int = 1) -> bool:
    info = _solo.get(user_id)
    return bool(info and info["extend_count"] < max_extends)

def extend_solo_mode(user_id: int, duration_days: int = 3) -> bool:
    info = _solo.get(user_id)
    if not info or info["extend_count"] >= 1:
        return False
    info["expires"] += duration_days * 86400
    info["extend_count"] += 1
    return True
