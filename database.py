# database.py

import time
import secrets

# ───────────────────────────────
# 1) 소유자 코드 관리 (_codes)
# ───────────────────────────────
# code -> { owner_id, expires }
_codes: dict[str, dict] = {}

def generate_code() -> str:
    """무작위 6자리 숫자 코드 생성"""
    return f"{secrets.randbelow(900000) + 100000}"

def register_code(owner_id: int, duration_days: int = 3) -> str:
    """새 코드 발급 및 만료일 설정, code 반환"""
    code = generate_code()
    expires = int(time.time()) + duration_days * 86400
    _codes[code] = {"owner": owner_id, "expires": expires}
    return code

def is_code_valid(code: str) -> bool:
    info = _codes.get(code)
    if not info:
        return False
    return info["expires"] >= int(time.time())

def code_remaining_seconds(code: str) -> int:
    """만료까지 남은 초. 만료되었으면 0 반환."""
    info = _codes.get(code)
    if not info:
        return 0
    return max(0, info["expires"] - int(time.time()))

# ───────────────────────────────
# 2) 그룹 등록 관리 (_groups)
# ───────────────────────────────
# group_id -> { code, expires, extend_count }
_groups: dict[int, dict] = {}

def register_group_to_code(code: str, group_id: int, duration_days: int = 3) -> bool:
    """
    그룹에 코드를 연결하고 3일 만료 타이머 시작.
    그룹당 하나의 코드만 허용, 중복 등록은 False.
    """
    if not is_code_valid(code):
        return False
    if group_id in _groups:
        return False
    now = int(time.time())
    _groups[group_id] = {
        "code": code,
        "expires": now + duration_days * 86400,
        "extend_count": 0
    }
    return True

def disconnect_user(update, context) -> None:
    """그룹 연결 해제(등록 정보 삭제)"""
    gid = update.effective_chat.id
    _groups.pop(gid, None)
    context.bot_data.get("is_group_registered", {}).pop(gid, None)
    update.message.reply_text("🔌 연결이 해제되었습니다.")

def is_group_active(group_id: int) -> bool:
    info = _groups.get(group_id)
    if not info:
        return False
    return info["expires"] >= int(time.time())

def extend_group(group_id: int, duration_days: int = 30, max_extends: int = 2) -> bool:
    """
    그룹 코드 연장: 최대 2회까지 30일씩 연장.
    성공하면 True, 실패(False) 반환.
    """
    info = _groups.get(group_id)
    if not info or info["extend_count"] >= max_extends:
        return False
    info["expires"] += duration_days * 86400
    info["extend_count"] += 1
    return True

def group_remaining_seconds(group_id: int) -> int:
    """그룹 코드 만료까지 남은 초. 없거나 만료 시 0."""
    info = _groups.get(group_id)
    if not info:
        return 0
    return max(0, info["expires"] - int(time.time()))
