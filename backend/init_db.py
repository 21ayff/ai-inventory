"""初始化数据库：建表 + 创建默认账号

运行方式：在 backend 目录下执行 `py init_db.py`
"""
from app.database import engine, Base, SessionLocal
from app import models  # 确保模型被注册
from app.models import User
from app.auth import hash_password

# 建表
Base.metadata.create_all(bind=engine)

# 创建默认账号
db = SessionLocal()
try:
    if db.query(User).filter(User.username == "admin").first():
        print("默认账号已存在，跳过")
    else:
        db.add(User(username="admin", password_hash=hash_password("admin123")))
        db.commit()
        print("默认账号创建成功：admin / admin123")
finally:
    db.close()
