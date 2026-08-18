"""全局配置"""
import os

# 项目根目录（backend 目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SQLite 数据库文件路径
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'inventory.db')}"

# JWT 密钥（生产环境请改成随机字符串并妥善保管）
SECRET_KEY = "ai-inventory-secret-key-please-change-in-production"

# JWT 算法
ALGORITHM = "HS256"

# token 有效期（天）
TOKEN_EXPIRE_DAYS = 7
