# database.py

import time
import secrets

# ────────────────────────────
# 1) 코드 관리
# ────────────────────────────
_codes: dict[str, dict] = {}     # code → { owner, expires, is_owner_code }
_groups: dict[int, dict] = {}    # group_id → { code, expires, extend_count, connected }

def generate_code() -> str:
    return f"{secrets.randbelow(900000) + 100000}"

def register_code(owner_id: int, duration_days: int = 3, max_free: int = 1) -> str | None:
    used = sum(
        1 for info in _codes.values()
        if info["owner"] == owner_id and not info.get("is_owner_code", False)
    )
    if used >= max_free:
        return None
    code = generate_code()
    _codes[code] = {
        "owner": owner_id,
        "expires": time.time() + duration_days * 86400,
        "is_owner_code": False
    }
    return code

def issue_owner_code(code: str, owner_id: int, duration_days: int):
    """소유자가 지정한 유효기간으로 코드 생성"""
    _codes[code] = {
        "owner": owner_id,
        "expires": time.time() + duration_days * 86400,
        "is_owner_code": True
    }

def is_code_valid(code: str) -> bool:
    info = _codes.get(code)
    return bool(info and info["expires"] >= time.time())

def delete_code(code: str) -> bool:
    if code not in _codes:
        return False
    del _codes[code]
    # 삭제 시 해당 코드로 연결된 그룹 모두 해제
    for grp in _groups.values():
        if grp["code"] == code:
            grp["connected"] = False
    return True

def extend_code(code: str, days: int) -> bool:
    """발급된 코드의 만료일 연장"""
    info = _codes.get(code)
    if not info:
        return False
    info["expires"] += days * 86400
    # 이미 연결된 그룹들의 만료도 동기화
    for grp in _groups.values():
        if grp["code"] == code and grp["connected"]:
            grp["expires"] = info["expires"]
    return True

# ────────────────────────────
# 2) 그룹 연결 관리
# ────────────────────────────
def register_group_to_code(code: str, group_id: int) -> bool:
    now = time.time()
    info_code = _codes.get(code)
    if not info_code or info_code["expires"] < now:
        return False

    if group_id in _groups:
        grp = _groups[group_id]
        if grp["code"] != code or grp["connected"]:
            return False
        grp["connected"] = True
        grp["expires"]   = info_code["expires"]
        return True

    _groups[group_id] = {
        "code":         code,
        "expires":      info_code["expires"],
        "extend_count": 0,
        "connected":    True
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
    info["expires"]      += duration_days * 86400
    info["extend_count"] += 1
    return True

def disconnect_user(group_id: int):
    info = _groups.get(group_id)
    if info:
        info["connected"] = False
