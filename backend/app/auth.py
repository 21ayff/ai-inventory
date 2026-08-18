"""密码加密与 JWT token 工具"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt

from .config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_DAYS


def hash_password(password: str) -> str:
    """使用 PBKDF2 加密密码，返回 salt$hash 格式"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    return f"{salt}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    """校验密码是否正确"""
    try:
        salt, expected = hashed.split("$", 1)
    except ValueError:
        return False
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100000)
    return secrets.compare_digest(dk.hex(), expected)


def create_token(user_id: int) -> str:
    """生成 JWT token"""
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> int:
    """解析 JWT token，返回 user_id；无效则抛出异常"""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return int(payload["sub"])
