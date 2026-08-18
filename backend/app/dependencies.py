"""鉴权依赖"""
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .auth import decode_token

# auto_error=False：没有 Authorization 头时不自动报错，让我们自定义提示
security = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """从请求头解析并校验 token，返回当前登录用户"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    try:
        user_id = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="登录已失效，请重新登录")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")

    return user
