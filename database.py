# database.py

import time
import secrets

# ────────────────────────────
# 데이터 저장소 초기화
# ────────────────────────────
_codes: dict[str, dict] = {}               # code → { owner, expires, is_owner_code }
_groups: dict[int, dict] = {}              # group_id → { code, expires, extend_count, connected }
_group_logs: dict[int, list[dict]] = {}    # group_id → list of { time, user_id, username, message }
_group_participants: dict[int, dict[int, str]] = {}  # group_id → { user_id: username }

# ────────────────────────────
# 1) 코드 관리
# ────────────────────────────

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


def issue_owner_code(code: str, owner_id: int, duration_days: int) -> None:
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
    # 삭제 시 해당 코드로 연결된 그룹 해제
    for grp in _groups.values():
        if grp["code"] == code:
            grp["connected"] = False
    return True


def extend_code(code: str, days: int) -> bool:
    """발급된 코드의 만료일 연장 및 연결된 그룹 동기화"""
    info = _codes.get(code)
    if not info:
        return False
    info["expires"] += days * 86400
    # 이미 연결된 그룹들의 만료일 동기화
    for grp in _groups.values():
        if grp.get("code") == code and grp.get("connected"):
            grp["expires"] = info["expires"]
    return True


def get_groups_by_code(code: str) -> list[int]:
    """해당 코드로 연결된 그룹 ID 목록 반환"""
    return [gid for gid, grp in _groups.items() if grp.get("code") == code]


def get_codes_by_owner(owner_id: int) -> list[str]:
    """소유자가 발급한 일반 코드 목록 반환"""
    return [c for c, info in _codes.items() if info["owner"] == owner_id and not info.get("is_owner_code", False)]


def get_owner_codes(owner_id: int) -> list[str]:
    """소유자 전용 코드 목록 반환"""
    return [c for c, info in _codes.items() if info["owner"] == owner_id and info.get("is_owner_code", False)]

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
        # 이미 다른 코드로 연결되어 있거나 이미 연결 상태면 거부
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
    return bool(info and info.get("connected") and info.get("expires", 0) >= time.time())


def group_remaining_seconds(group_id: int) -> int:
    info = _groups.get(group_id)
    if not info:
        return 0
    return max(0, int(info["expires"] - time.time()))


def extend_group(group_id: int, duration_days: int = 3, max_extends: int = 1) -> bool:
    info = _groups.get(group_id)
    if not info or info.get("extend_count", 0) >= max_extends:
        return False
    info["expires"]      += duration_days * 86400
    info["extend_count"] += 1
    return True


def disconnect_user(group_id: int) -> None:
    info = _groups.get(group_id)
    if info:
        info["connected"] = False

# ────────────────────────────
# 3) 그룹 메시지 로그 및 참가자 관리
# ────────────────────────────

def register_participant(group_id: int, user_id: int, username: str) -> None:
    """그룹 참가자를 등록"""
    if group_id not in _group_participants:
        _group_participants[group_id] = {}
    _group_participants[group_id][user_id] = username


def list_group_participants(group_id: int) -> list[tuple[int, str]]:
    """그룹 참가자 목록 반환"""
    return list(_group_participants.get(group_id, {}).items())


def log_group_message(group_id: int, user_id: int, username: str, message: str, timestamp: float = None) -> None:
    """그룹 메시지를 로그에 저장"""
    ts = timestamp if timestamp is not None else time.time()
    if group_id not in _group_logs:
        _group_logs[group_id] = []
    _group_logs[group_id].append({
        "time": ts,
        "user_id": user_id,
        "username": username,
        "message": message
    })
    # 메시지를 남기면 자동으로 참가자도 등록
    register_participant(group_id, user_id, username)


def get_group_logs(group_id: int, limit: int | None = None) -> list[dict]:
    """그룹 로그를 반환 (최신 limit개 선택 가능)"""
    logs = _group_logs.get(group_id, [])
    return logs[-limit:] if limit else logs
