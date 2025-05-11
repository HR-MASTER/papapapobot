# database.py
import sqlite3
import time
from typing import Optional, Tuple

# SQLite DB 연결 (동일 프로세스내 캐시)
_conn = sqlite3.connect("app.db", check_same_thread=False)
_cur = _conn.cursor()

# ─────────────────────────────
# 1) 스키마 초기화
# ─────────────────────────────
_cur.execute("""
CREATE TABLE IF NOT EXISTS codes (
    code TEXT PRIMARY KEY,
    owner_id INTEGER NOT NULL,
    expires INTEGER NOT NULL
)
""")
_cur.execute("""
CREATE TABLE IF NOT EXISTS groups (
    group_id INTEGER PRIMARY KEY,
    code TEXT NOT NULL,
    expires INTEGER NOT NULL,
    extend_count INTEGER NOT NULL,
    last_payment_check INTEGER NOT NULL
)
""")
_cur.execute("""
CREATE TABLE IF NOT EXISTS solos (
    user_id INTEGER PRIMARY KEY,
    expires INTEGER NOT NULL,
    extend_count INTEGER NOT NULL
)
""")
_conn.commit()


# ─────────────────────────────
# 2) 코드 관리 함수
# ─────────────────────────────
def register_code(owner_id: int, code: str, duration_days: int) -> None:
    """코드를 저장소에 등록"""
    expires = int(time.time()) + duration_days * 86400
    _cur.execute("INSERT OR REPLACE INTO codes(code,owner_id,expires) VALUES(?,?,?)",
                 (code, owner_id, expires))
    _conn.commit()

def is_code_valid(code: str) -> bool:
    """코드 존재 및 만료 여부 확인"""
    _cur.execute("SELECT expires FROM codes WHERE code = ?", (code,))
    row = _cur.fetchone()
    return bool(row and row[0] >= int(time.time()))

def code_remaining_seconds(code: str) -> int:
    """코드 만료까지 남은 초 반환"""
    _cur.execute("SELECT expires FROM codes WHERE code = ?", (code,))
    row = _cur.fetchone()
    if not row: return 0
    return max(0, row[0] - int(time.time()))


# ─────────────────────────────
# 3) 그룹 연결 관리 함수
# ─────────────────────────────
def register_group_to_code(code: str, group_id: int, duration_days: int) -> bool:
    """그룹에 코드 등록 및 타이머 설정"""
    if not is_code_valid(code):
        return False
    now = int(time.time())
    expires = now + duration_days * 86400
    try:
        _cur.execute("""
            INSERT INTO groups(group_id,code,expires,extend_count,last_payment_check)
            VALUES(?,?,?,?,?)
        """, (group_id, code, expires, 0, now))
    except sqlite3.IntegrityError:
        return False
    _conn.commit()
    return True

def is_group_active(group_id: int) -> bool:
    """그룹 등록 및 만료 여부 확인"""
    _cur.execute("SELECT expires FROM groups WHERE group_id = ?", (group_id,))
    row = _cur.fetchone()
    return bool(row and row[0] >= int(time.time()))

def group_remaining_seconds(group_id: int) -> int:
    """그룹 코드 만료까지 남은 초"""
    _cur.execute("SELECT expires FROM groups WHERE group_id = ?", (group_id,))
    row = _cur.fetchone()
    if not row: return 0
    return max(0, row[0] - int(time.time()))

def extend_group(group_id: int, duration_days: int, max_extends: int) -> bool:
    """그룹 코드 연장 (최대 max_extends회)"""
    _cur.execute("SELECT expires,extend_count FROM groups WHERE group_id = ?",
                 (group_id,))
    row = _cur.fetchone()
    if not row or row[1] >= max_extends:
        return False
    new_expires = row[0] + duration_days * 86400
    new_count = row[1] + 1
    _cur.execute("UPDATE groups SET expires = ?, extend_count = ? WHERE group_id = ?",
                 (new_expires, new_count, group_id))
    _conn.commit()
    return True

def update_last_payment_check(group_id: int, timestamp: int) -> None:
    """마지막 결제 확인 시각(ms) 저장"""
    _cur.execute("UPDATE groups SET last_payment_check = ? WHERE group_id = ?",
                 (timestamp, group_id))
    _conn.commit()

def get_last_payment_check(group_id: int) -> int:
    """마지막 결제 확인 시각(ms) 조회"""
    _cur.execute("SELECT last_payment_check FROM groups WHERE group_id = ?",
                 (group_id,))
    row = _cur.fetchone()
    return row[0] if row else 0

def disconnect_user(group_id: int) -> None:
    """그룹 등록 해제"""
    _cur.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))
    _conn.commit()


# ─────────────────────────────
# 4) 솔로 모드 관리 함수
# ─────────────────────────────
def activate_solo_mode(user_id: int, duration_days: int) -> None:
    """솔로 모드 활성화"""
    expires = int(time.time()) + duration_days * 86400
    _cur.execute("INSERT OR REPLACE INTO solos(user_id,expires,extend_count) VALUES(?,?,?)",
                 (user_id, expires, 0))
    _conn.commit()

def is_solo_mode_active(user_id: int) -> bool:
    """솔로 모드 활성 여부"""
    _cur.execute("SELECT expires FROM solos WHERE user_id = ?", (user_id,))
    row = _cur.fetchone()
    return bool(row and row[0] >= int(time.time()))

def can_extend_solo_mode(user_id: int, max_extends: int) -> bool:
    """솔로 모드 연장 가능 여부"""
    _cur.execute("SELECT extend_count FROM solos WHERE user_id = ?", (user_id,))
    row = _cur.fetchone()
    return bool(row and row[0] < max_extends)

def extend_solo_mode(user_id: int, duration_days: int) -> bool:
    """솔로 모드 연장"""
    _cur.execute("SELECT expires,extend_count FROM solos WHERE user_id = ?", (user_id,))
    row = _cur.fetchone()
    if not row or row[1] >= 1:
        return False
    new_expires = row[0] + duration_days * 86400
    new_count = row[1] + 1
    _cur.execute("UPDATE solos SET expires = ?, extend_count = ? WHERE user_id = ?",
                 (new_expires, new_count, user_id))
    _conn.commit()
    return True
