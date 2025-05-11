# database.py

import time
import secrets

# ───────────────────────────────
# 1) 사용자 코드(소유자) 관리 (_codes)
# ───────────────────────────────
# code -> { owner, expires }
_codes: dict[str, dict] = {}

def generate_code() -> str:
    """무작위 6자리 숫자 코드 생성"""
    return f"{secrets.randbelow(900000) + 100000}"

def register_code(owner_id: int, duration_days: int = 3) -> str:
    """새 코드 발급 및 만료일 설정, 코드 반환"""
    code = generate_code()
    expires = int(time.time()) + duration_days * 86400
    _codes[code] = {"owner": owner_id, "expires": expires}
    return code

def is_code_valid(code: str) -> bool:
    """코드가 존재하고 만료되지 않았는지 확인"""
    info = _codes.get(code)
    return bool(info and info["expires"] >= time.time())

def code_remaining_seconds(code: str) -> int:
    """코드 만료까지 남은 초. 만료 시 0 반환."""
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
    """
    그룹에 코드를 연결하고 만료 타이머 시작.
    이미 연결되거나 유효하지 않으면 False.
    """
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
    """그룹에 코드가 연결되어 있고 만료되지 않았는지 확인"""
    info = _groups.get(group_id)
    return bool(info and info["expires"] >= time.time())

def group_remaining_seconds(group_id: int) -> int:
    """그룹 코드 만료까지 남은 초. 만료 시 0."""
    info = _groups.get(group_id)
    if not info:
        return 0
    return max(0, int(info["expires"] - time.time()))

def extend_group(group_id: int, duration_days: int = 30, max_extends: int = 2) -> bool:
    """
    그룹 코드 연장: 최대 max_extends회, 각 duration_days만큼.
    성공 시 True, 실패 시 False.
    """
    info = _groups.get(group_id)
    if not info or info["extend_count"] >= max_extends:
        return False
    info["expires"] += duration_days * 86400
    info["extend_count"] += 1
    return True

def update_last_payment_check(group_id: int, timestamp_ms: int):
    """트랜젝션 조회 시각 기록"""
    info = _groups.get(group_id)
    if info:
        info["last_payment_check"] = timestamp_ms

def get_last_payment_check(group_id: int) -> int:
    """마지막 트랜잭션 조회 시각(ms) 반환"""
    return _groups.get(group_id, {}).get("last_payment_check", 0)

def disconnect_user(update, context) -> None:
    """그룹 연결 해제(등록 정보 삭제)"""
    gid = update.effective_chat.id
    _groups.pop(gid, None)
    context.bot_data.get("is_group_registered", {}).pop(gid, None)
    update.message.reply_text("🔌 연결이 해제되었습니다.")

# ───────────────────────────────
# 3) 솔로모드 관리 (_solo)
# ───────────────────────────────
# user_id -> { expires, extend_count }
_solo: dict[int, dict] = {}

def activate_solo_mode(user_id: int, duration_days: int = 3):
    """솔로 모드 시작 및 연장 횟수 초기화"""
    now = int(time.time())
    _solo[user_id] = {
        "expires": now + duration_days * 86400,
        "extend_count": 0
    }

def is_solo_mode_active(user_id: int) -> bool:
    """솔로 모드가 활성 상태인지 확인"""
    info = _solo.get(user_id)
    return bool(info and info["expires"] >= int(time.time()))

def can_extend_solo_mode(user_id: int, max_extends: int = 1) -> bool:
    """솔로 모드 연장 가능 여부 (최대 1회 추가 연장)"""
    info = _solo.get(user_id)
    return bool(info and info["extend_count"] < max_extends)

def extend_solo_mode(user_id: int, duration_days: int = 3) -> bool:
    """솔로 모드를 duration_days만큼 연장 (최대 한 번)"""
    info = _solo.get(user_id)
    if not info or info["extend_count"] >= 1:
        return False
    info["expires"] += duration_days * 86400
    info["extend_count"] += 1
    return True
