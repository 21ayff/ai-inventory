"""登录与注册接口"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserRegister, UserLogin, TokenResponse, ChangePasswordRequest
from ..auth import hash_password, verify_password, create_token
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """注册新用户"""
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")

    exists = db.query(User).filter(User.username == data.username).first()
    if exists:
        raise HTTPException(status_code=400, detail="用户名已存在")

    user = User(username=data.username, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_token(user.id)
    return TokenResponse(access_token=token, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """登录"""
    user = db.query(User).filter(User.username == data.username).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_token(user.id)
    return TokenResponse(access_token=token, username=user.username)


@router.get("/me")
def get_me(username: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """获取当前用户信息"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"username": user.username, "created_at": user.created_at}


@router.post("/change-password")
def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """修改密码（需验证旧密码）"""
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="旧密码错误")

    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")

    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "密码修改成功"}
