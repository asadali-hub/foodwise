
import hashlib
import hmac
import secrets
import time

from .database import get_conn

SESSION_DURATION = 8 * 60 * 60
_sessions = {}


def init_auth():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def admin_exists():
    conn = get_conn()
    row = conn.execute(
        "SELECT id FROM admin_users LIMIT 1"
    ).fetchone()
    conn.close()
    return row is not None


def create_admin(username, password):
    username = username.strip()

    if len(username) < 3:
        return False, "Username must have at least 3 characters."

    if len(password) < 8:
        return False, "Password must have at least 8 characters."

    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310000
    )

    conn = get_conn()

    try:
        conn.execute("""
            INSERT INTO admin_users
            (username, password_hash, salt)
            VALUES (?, ?, ?)
        """, (
            username,
            password_hash.hex(),
            salt.hex()
        ))
        conn.commit()
        return True, "Admin account created."

    except Exception:
        return False, "Could not create admin account."

    finally:
        conn.close()


def verify_admin(username, password):
    conn = get_conn()

    row = conn.execute("""
        SELECT password_hash, salt
        FROM admin_users
        WHERE username = ?
    """, (username.strip(),)).fetchone()

    conn.close()

    if not row:
        return False

    salt = bytes.fromhex(row["salt"])
    expected_hash = bytes.fromhex(row["password_hash"])

    actual_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        310000
    )

    return hmac.compare_digest(actual_hash, expected_hash)


def create_session(username):
    token = secrets.token_urlsafe(32)

    _sessions[token] = {
        "username": username,
        "expires": time.time() + SESSION_DURATION
    }

    return token


def get_session(token):
    session = _sessions.get(token)

    if not session:
        return None

    if time.time() > session["expires"]:
        _sessions.pop(token, None)
        return None

    return session


def delete_session(token):
    _sessions.pop(token, None)
