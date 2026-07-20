"""Accounts: register/login with id+password, server-saved progress.

Security: passwords are stored only as salted PBKDF2-SHA256 hashes. Sessions
are random tokens in a tokens table (multiple devices can stay logged in).

Storage: SQLite (data/users.db) by default — zero setup, perfect locally.
If a DATABASE_URL env var is set (e.g. a free Neon/Supabase Postgres), that is
used instead, which makes accounts durable on hosts with ephemeral disks
(Render's free tier resets its disk on every deploy/restart).

Progress payload is an opaque JSON blob owned by the client:
  { rating, history, bestLevel, puzzles }
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import smtplib
import ssl
import time
import unicodedata
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# email (optional) — send password-reset codes. Two providers, checked in order:
#   1. Resend (HTTP API, no app password):  RESEND_API_KEY, RESEND_FROM
#   2. SMTP (e.g. Gmail):  SMTP_HOST (default smtp.gmail.com), SMTP_PORT (465),
#                          SMTP_USER, SMTP_PASS, SMTP_FROM (default = SMTP_USER)
# If neither is configured, email is disabled and accounts fall back to the
# one-time recovery code.
# --------------------------------------------------------------------------- #
_RESEND_KEY = os.environ.get("RESEND_API_KEY", "").strip()
# Resend needs a verified sender. Until you verify your own domain you can only
# use "onboarding@resend.dev" (the default), which delivers to your OWN Resend
# account email. Set RESEND_FROM to "Matevio <you@yourdomain>" once verified.
_RESEND_FROM = os.environ.get("RESEND_FROM", "").strip() or "Matevio <onboarding@resend.dev>"

_SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
_SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
_SMTP_USER = os.environ.get("SMTP_USER", "").strip()
# Google shows app passwords as "abcd efgh ijkl mnop"; strip spaces so a
# copy-paste with the display spaces still logs in.
_SMTP_PASS = os.environ.get("SMTP_PASS", "").replace(" ", "")
_SMTP_FROM = os.environ.get("SMTP_FROM", "").strip() or _SMTP_USER

# Brevo (HTTP API) — no domain needed: verify a single sender email, then send
# to anyone. BREVO_FROM must be that verified sender address.
_BREVO_KEY = os.environ.get("BREVO_API_KEY", "").strip()
_BREVO_FROM = os.environ.get("BREVO_FROM", "").strip() or _SMTP_FROM
_BREVO_FROM_NAME = os.environ.get("BREVO_FROM_NAME", "").strip() or "Matevio"

_EMAIL_ENABLED = bool(_BREVO_KEY) or bool(_RESEND_KEY) or bool(_SMTP_USER and _SMTP_PASS)
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _valid_email(e: str | None):
    e = (e or "").strip()
    return e if (_EMAIL_RE.match(e) and len(e) <= 120) else None


def _mask_email(e: str) -> str:
    try:
        name, dom = e.split("@", 1)
        head = name[:2] if len(name) > 2 else name[:1]
        return f"{head}{'*' * max(2, len(name) - len(head))}@{dom}"
    except Exception:
        return "***"


def _send_via_resend(to_addr: str, subject: str, body: str) -> bool:
    payload = json.dumps({
        "from": _RESEND_FROM,
        "to": [to_addr],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {_RESEND_KEY}",
            "Content-Type": "application/json",
            # Cloudflare in front of api.resend.com blocks the default
            # "Python-urllib" UA (error 1010); send a normal UA instead.
            "User-Agent": "Matevio/1.0 (+https://matevio.com)",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return 200 <= resp.status < 300


def _send_via_brevo(to_addr: str, subject: str, body: str) -> bool:
    payload = json.dumps({
        "sender": {"email": _BREVO_FROM, "name": _BREVO_FROM_NAME},
        "to": [{"email": to_addr}],
        "subject": subject,
        "textContent": body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=payload,
        headers={
            "api-key": _BREVO_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Matevio/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return 200 <= resp.status < 300


def _send_via_smtp(to_addr: str, subject: str, body: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _SMTP_FROM
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP_SSL(_SMTP_HOST, _SMTP_PORT, context=ssl.create_default_context(), timeout=15) as s:
        s.login(_SMTP_USER, _SMTP_PASS)
        s.send_message(msg)
    return True


def _send_email(to_addr: str, subject: str, body: str) -> bool:
    if not _EMAIL_ENABLED:
        return False
    # Provider priority: Brevo → Resend → SMTP. Retry the HTTP providers a couple
    # of times to ride out transient 5xx / edge challenges.
    if _BREVO_KEY:
        provider, attempts = _send_via_brevo, 3
    elif _RESEND_KEY:
        provider, attempts = _send_via_resend, 3
    else:
        provider, attempts = _send_via_smtp, 1
    for i in range(attempts):
        try:
            return provider(to_addr, subject, body)
        except Exception:
            if i == attempts - 1:
                return False
            time.sleep(1.0)
    return False

_HERE = os.path.dirname(os.path.abspath(__file__))
_SQLITE_PATH = os.path.join(os.path.dirname(_HERE), "data", "users.db")
_PG_URL = os.environ.get("DATABASE_URL", "").strip()
_IS_PG = _PG_URL.startswith(("postgres://", "postgresql://"))

_ID_RE = re.compile(r"^[A-Za-z0-9_\-가-힣]{2,20}$")
_MAX_PROGRESS_BYTES = 200_000


# --------------------------------------------------------------------------- #
# storage layer (same SQL on both backends; only placeholders differ)
# --------------------------------------------------------------------------- #
def _connect():
    if _IS_PG:
        import psycopg
        return psycopg.connect(_PG_URL)
    import sqlite3
    os.makedirs(os.path.dirname(_SQLITE_PATH), exist_ok=True)
    return sqlite3.connect(_SQLITE_PATH)


def _ph() -> str:
    return "%s" if _IS_PG else "?"


def _init_db() -> None:
    with _connect() as con:
        cur = con.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            pw_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            progress TEXT NOT NULL DEFAULT '{}',
            created TEXT)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created TEXT)""")
        # recovery code (hashed) — lets a user reset a forgotten password without email
        cur.execute("""CREATE TABLE IF NOT EXISTS recovery (
            user_id TEXT PRIMARY KEY,
            code_hash TEXT NOT NULL,
            salt TEXT NOT NULL)""")
        # optional email (for emailed reset codes)
        cur.execute("""CREATE TABLE IF NOT EXISTS user_email (
            user_id TEXT PRIMARY KEY,
            email TEXT NOT NULL)""")
        # short-lived emailed reset codes
        cur.execute("""CREATE TABLE IF NOT EXISTS reset_codes (
            user_id TEXT PRIMARY KEY,
            code_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            expires TEXT NOT NULL)""")
        con.commit()


def _hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


# recovery codes: unambiguous alphabet (no 0/O/1/I), shown grouped, matched loosely
_RCHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _gen_recovery() -> str:
    s = "".join(secrets.choice(_RCHARS) for _ in range(12))
    return f"{s[0:4]}-{s[4:8]}-{s[8:12]}"


def _norm_code(c: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (c or "").upper())


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_user(con, uid: str):
    cur = con.cursor()
    cur.execute(f"SELECT id, pw_hash, salt, progress FROM users WHERE id = {_ph()}", (uid,))
    return cur.fetchone()


def _user_for_token(con, token: str):
    cur = con.cursor()
    cur.execute(f"SELECT user_id FROM tokens WHERE token = {_ph()}", (token,))
    row = cur.fetchone()
    return row[0] if row else None


def _issue_token(con, uid: str) -> str:
    token = secrets.token_hex(24)
    con.cursor().execute(
        f"INSERT INTO tokens (token, user_id, created) VALUES ({_ph()}, {_ph()}, {_ph()})",
        (token, uid, _now()))
    return token


# --------------------------------------------------------------------------- #
# request models
# --------------------------------------------------------------------------- #
class RegisterRequest(BaseModel):
    id: str
    pw: str
    email: str | None = None
    progress: dict | None = None


class IdRequest(BaseModel):
    id: str


class LoginRequest(BaseModel):
    id: str
    pw: str


class ResetRequest(BaseModel):
    id: str
    code: str
    pw: str


class TokenRequest(BaseModel):
    token: str


class SaveRequest(BaseModel):
    token: str
    progress: dict


# Korean text can arrive either precomposed (NFC) or decomposed (NFD, common on
# iOS/macOS keyboards). Without normalization the *same* id/password produces a
# different byte string → different hash → "wrong password" even when it's right.
# Normalize both to NFC everywhere so register and login always agree.
def _norm_id(raw: str) -> str:
    uid = unicodedata.normalize("NFC", raw or "").strip()
    if not _ID_RE.match(uid):
        raise HTTPException(400, "아이디는 2~20자의 한글/영문/숫자/_/- 만 가능합니다.")
    return uid.lower() if uid.isascii() else uid


def _norm_pw(pw: str) -> str:
    return unicodedata.normalize("NFC", pw if isinstance(pw, str) else "")


def _check_pw(pw: str) -> str:
    pw = _norm_pw(pw)
    if not (4 <= len(pw) <= 64):
        raise HTTPException(400, "비밀번호는 4자 이상이어야 합니다.")
    return pw


def _progress_json(progress: dict | None) -> str:
    txt = json.dumps(progress or {}, ensure_ascii=False)
    if len(txt.encode()) > _MAX_PROGRESS_BYTES:
        raise HTTPException(400, "진행 데이터가 너무 큽니다.")
    return txt


# --------------------------------------------------------------------------- #
def register_auth(app: FastAPI) -> None:
    _init_db()

    @app.post("/api/auth/register")
    def auth_register(req: RegisterRequest):
        uid = _norm_id(req.id)
        pw = _check_pw(req.pw)
        progress = _progress_json(req.progress)
        rcode = _gen_recovery()
        email = _valid_email(req.email)
        with _connect() as con:
            cur = con.cursor()
            if _get_user(con, uid) is not None:
                raise HTTPException(409, "이미 사용 중인 아이디입니다.")
            salt = secrets.token_hex(16)
            cur.execute(
                f"INSERT INTO users (id, pw_hash, salt, progress, created) "
                f"VALUES ({_ph()}, {_ph()}, {_ph()}, {_ph()}, {_ph()})",
                (uid, _hash_pw(pw, salt), salt, progress, _now()))
            rsalt = secrets.token_hex(16)
            cur.execute(
                f"INSERT INTO recovery (user_id, code_hash, salt) VALUES ({_ph()}, {_ph()}, {_ph()})",
                (uid, _hash_pw(_norm_code(rcode), rsalt), rsalt))
            if email:
                cur.execute(f"INSERT INTO user_email (user_id, email) VALUES ({_ph()}, {_ph()})", (uid, email))
            token = _issue_token(con, uid)
            con.commit()
        # `recovery` returned ONCE; the client shows it only if no email was given
        return {"ok": True, "id": uid, "token": token, "recovery": rcode,
                "hasEmail": bool(email), "progress": json.loads(progress)}

    @app.post("/api/auth/login")
    def auth_login(req: LoginRequest):
        uid = _norm_id(req.id)
        with _connect() as con:
            row = _get_user(con, uid)
            if row is None or _hash_pw(_norm_pw(req.pw), row[2]) != row[1]:
                time.sleep(0.3)          # slow brute-force attempts
                raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
            token = _issue_token(con, uid)
            con.commit()
            return {"ok": True, "id": row[0], "token": token,
                    "progress": json.loads(row[3] or "{}")}

    @app.post("/api/auth/request_reset")
    def auth_request_reset(req: IdRequest):
        """Email a short-lived reset code to the account's email (if any)."""
        uid = _norm_id(req.id)
        with _connect() as con:
            cur = con.cursor()
            if _get_user(con, uid) is None:
                return {"ok": True, "emailed": False}    # don't leak which ids exist
            cur.execute(f"SELECT email FROM user_email WHERE user_id = {_ph()}", (uid,))
            row = cur.fetchone()
            email = row[0] if row else None
            if not (email and _EMAIL_ENABLED):
                return {"ok": True, "emailed": False}    # fall back to the recovery code
            code = f"{secrets.randbelow(1000000):06d}"
            salt = secrets.token_hex(16)
            expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
            cur.execute(f"DELETE FROM reset_codes WHERE user_id = {_ph()}", (uid,))
            cur.execute(
                f"INSERT INTO reset_codes (user_id, code_hash, salt, expires) VALUES ({_ph()}, {_ph()}, {_ph()}, {_ph()})",
                (uid, _hash_pw(code, salt), salt, expires))
            con.commit()
        sent = _send_email(
            email, "Matevio 비밀번호 재설정 코드",
            f"Matevio 비밀번호 재설정 코드는 [ {code} ] 입니다.\n\n앱에서 15분 안에 입력하세요.\n"
            f"본인이 요청하지 않았다면 이 메일을 무시하셔도 됩니다.")
        return {"ok": True, "emailed": bool(sent), "email_hint": _mask_email(email)}

    @app.post("/api/auth/reset")
    def auth_reset(req: ResetRequest):
        """Reset a forgotten password with an emailed code OR the recovery code."""
        uid = _norm_id(req.id)
        newpw = _check_pw(req.pw)
        raw = req.code or ""
        ok = False
        with _connect() as con:
            cur = con.cursor()
            # 1) emailed reset code (6 digits, time-limited)
            cur.execute(f"SELECT code_hash, salt, expires FROM reset_codes WHERE user_id = {_ph()}", (uid,))
            rc = cur.fetchone()
            if rc and rc[2] and _now() <= rc[2] and _hash_pw(re.sub(r"\s", "", raw), rc[1]) == rc[0]:
                ok = True
            # 2) recovery code (from sign-up)
            if not ok:
                cur.execute(f"SELECT code_hash, salt FROM recovery WHERE user_id = {_ph()}", (uid,))
                rr = cur.fetchone()
                if rr and _hash_pw(_norm_code(raw), rr[1]) == rr[0]:
                    ok = True
            if not ok:
                time.sleep(0.3)
                raise HTTPException(401, "아이디 또는 코드가 올바르지 않습니다.")
            salt = secrets.token_hex(16)
            cur.execute(f"UPDATE users SET pw_hash = {_ph()}, salt = {_ph()} WHERE id = {_ph()}",
                        (_hash_pw(newpw, salt), salt, uid))
            rcode = _gen_recovery()
            rsalt = secrets.token_hex(16)
            cur.execute(f"UPDATE recovery SET code_hash = {_ph()}, salt = {_ph()} WHERE user_id = {_ph()}",
                        (_hash_pw(_norm_code(rcode), rsalt), rsalt, uid))
            cur.execute(f"DELETE FROM reset_codes WHERE user_id = {_ph()}", (uid,))
            cur.execute(f"DELETE FROM tokens WHERE user_id = {_ph()}", (uid,))   # log out other sessions
            token = _issue_token(con, uid)
            urow = _get_user(con, uid)
            con.commit()
        return {"ok": True, "id": uid, "token": token, "progress": json.loads(urow[3] or "{}")}

    @app.post("/api/auth/logout")
    def auth_logout(req: TokenRequest):
        with _connect() as con:
            con.cursor().execute(f"DELETE FROM tokens WHERE token = {_ph()}", (req.token,))
            con.commit()
        return {"ok": True}

    @app.post("/api/auth/delete")
    def auth_delete(req: TokenRequest):
        """Permanently delete the account and ALL its server-stored data."""
        with _connect() as con:
            uid = _user_for_token(con, req.token)
            if uid is None:
                raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인하세요.")
            cur = con.cursor()
            cur.execute(f"DELETE FROM tokens WHERE user_id = {_ph()}", (uid,))
            cur.execute(f"DELETE FROM recovery WHERE user_id = {_ph()}", (uid,))
            cur.execute(f"DELETE FROM user_email WHERE user_id = {_ph()}", (uid,))
            cur.execute(f"DELETE FROM reset_codes WHERE user_id = {_ph()}", (uid,))
            cur.execute(f"DELETE FROM users WHERE id = {_ph()}", (uid,))
            con.commit()
        return {"ok": True}

    @app.post("/api/auth/load")
    def auth_load(req: TokenRequest):
        with _connect() as con:
            uid = _user_for_token(con, req.token)
            if uid is None:
                raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인하세요.")
            row = _get_user(con, uid)
            return {"ok": True, "id": uid, "progress": json.loads(row[3] or "{}")}

    @app.get("/api/leaderboard")
    def leaderboard():
        """Top registered accounts by rating (from their saved progress)."""
        with _connect() as con:
            cur = con.cursor()
            cur.execute("SELECT id, progress FROM users")
            rows = cur.fetchall()
        entries = []
        for uid, prog in rows:
            try:
                rating = int(json.loads(prog or "{}").get("rating", 0) or 0)
            except (ValueError, TypeError, json.JSONDecodeError):
                rating = 0
            entries.append({"id": uid, "rating": max(0, rating)})
        entries.sort(key=lambda e: -e["rating"])
        return {"ok": True, "top": entries[:20], "total": len(entries)}

    @app.post("/api/auth/save")
    def auth_save(req: SaveRequest):
        progress = _progress_json(req.progress)
        with _connect() as con:
            uid = _user_for_token(con, req.token)
            if uid is None:
                raise HTTPException(401, "세션이 만료되었습니다. 다시 로그인하세요.")
            con.cursor().execute(
                f"UPDATE users SET progress = {_ph()} WHERE id = {_ph()}", (progress, uid))
            con.commit()
        return {"ok": True}
