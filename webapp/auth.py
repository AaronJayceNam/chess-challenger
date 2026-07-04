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
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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
        con.commit()


def _hash_pw(pw: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


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
    progress: dict | None = None


class LoginRequest(BaseModel):
    id: str
    pw: str


class TokenRequest(BaseModel):
    token: str


class SaveRequest(BaseModel):
    token: str
    progress: dict


def _norm_id(raw: str) -> str:
    uid = (raw or "").strip()
    if not _ID_RE.match(uid):
        raise HTTPException(400, "아이디는 2~20자의 한글/영문/숫자/_/- 만 가능합니다.")
    return uid.lower() if uid.isascii() else uid


def _check_pw(pw: str) -> str:
    if not isinstance(pw, str) or not (4 <= len(pw) <= 64):
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
        with _connect() as con:
            if _get_user(con, uid) is not None:
                raise HTTPException(409, "이미 사용 중인 아이디입니다.")
            salt = secrets.token_hex(16)
            con.cursor().execute(
                f"INSERT INTO users (id, pw_hash, salt, progress, created) "
                f"VALUES ({_ph()}, {_ph()}, {_ph()}, {_ph()}, {_ph()})",
                (uid, _hash_pw(pw, salt), salt, progress, _now()))
            token = _issue_token(con, uid)
            con.commit()
        return {"ok": True, "id": uid, "token": token, "progress": json.loads(progress)}

    @app.post("/api/auth/login")
    def auth_login(req: LoginRequest):
        uid = _norm_id(req.id)
        with _connect() as con:
            row = _get_user(con, uid)
            if row is None or _hash_pw(req.pw or "", row[2]) != row[1]:
                time.sleep(0.3)          # slow brute-force attempts
                raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
            token = _issue_token(con, uid)
            con.commit()
            return {"ok": True, "id": row[0], "token": token,
                    "progress": json.loads(row[3] or "{}")}

    @app.post("/api/auth/logout")
    def auth_logout(req: TokenRequest):
        with _connect() as con:
            con.cursor().execute(f"DELETE FROM tokens WHERE token = {_ph()}", (req.token,))
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
