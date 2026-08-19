"""初始化数据库：建表 + 创建默认账号 + 初始化默认配置

运行方式：在 backend 目录下执行 `py init_db.py`
"""
from app.database import engine, Base, SessionLocal
from app import models  # 确保模型被注册
from app.models import User, Setting
from app.auth import hash_password

# 建表
Base.metadata.create_all(bind=engine)

# 默认配置项
DEFAULT_SETTINGS = {
    "order_cost": "20",          # 每次订货成本（元/次，便利店单SKU分摊成本）
    "holding_cost_rate": "0.25", # 持有成本率（成本价 × 25%）
}

# 创建默认账号 + 初始化配置
db = SessionLocal()
try:
    # 创建默认账号
    if db.query(User).filter(User.username == "admin").first():
        print("默认账号已存在，跳过")
    else:
        db.add(User(username="admin", password_hash=hash_password("admin123")))
        db.commit()
        print("默认账号创建成功：admin / admin123")

    # 初始化默认配置
    for key, value in DEFAULT_SETTINGS.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if not existing:
            db.add(Setting(key=key, value=value))
    db.commit()
    print("默认配置初始化完成")
finally:
    db.close()
