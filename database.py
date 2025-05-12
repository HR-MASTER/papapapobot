# database.py

import time
import secrets

# ────────────────────────────
# 1) 사용자 코드(소유자) 관리
# ────────────────────────────
_codes: dict[str, dict] = {}

def generate_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

def register_code(owner_id: int, duration_days: int = 3, max_free: int = 1) -> str | None:
    # 사용자당 무료 코드 발급 최대 max_free 회
    used = sum(1 for info in _codes.values() if info["owner"] == owner_id)
    if used >= max_free:
        return None
    code = generate_code()
    expires = time.time() + duration_days * 86400
    _codes[code] = {"owner": owner_id, "expires": expires}
    return code

def is_code_valid(code: str) -> bool:
    info = _codes.get(code)
    return bool(info and info["expires"] >= time.time())

# ────────────────────────────
# 2) 그룹 연결 관리
# ────────────────────────────
_groups: dict[int, dict] = {}

def register_group_to_code(code: str, group_id: int, duration_days: int = 3) -> bool:
    now = time.time()
    info = _groups.get(group_id)
    if info:
        # 이미 연결된 그룹이면 재등록 불가
        if info["code"] != code or info["connected"]:
            return False
        info["connected"] = True
        return True
    if not is_code_valid(code):
        return False
    _groups[group_id] = {
        "code": code,
        "expires": now + duration_days * 86400,
        "extend_count": 0,
        "connected": True
    }
    return True

def is_group_active(group_id: int) -> bool:
    info = _groups.get(group_id)
    return bool(info and info["connected"] and info["expires"] >= time.time())

def group_remaining_seconds(group_id: int) -> int:
    info = _groups.get(group_id)
    if not info:
        return 0
    return max(0, int(info["expires"] - time.time()))

def extend_group(group_id: int, duration_days: int = 3, max_extends: int = 1) -> bool:
    info = _groups.get(group_id)
    if not info or info["extend_count"] >= max_extends:
        return False
    info["expires"] += duration_days * 86400
    info["extend_count"] += 1
    return True

def disconnect_user(group_id: int):
    info = _groups.get(group_id)
    if info:
        info["connected"] = False
