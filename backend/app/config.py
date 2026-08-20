"""全局配置"""
import os

# 项目根目录（backend 目录）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SQLite 数据库文件路径（存在项目 backend 目录下，用正斜杠避免 Windows 路径问题）
_db_path = os.path.join(BASE_DIR, 'inventory.db').replace(chr(92), '/')
DATABASE_URL = f"sqlite:///{_db_path}"

# JWT 密钥（生产环境请改成随机字符串并妥善保管）
SECRET_KEY = "ai-inventory-secret-key-please-change-in-production"

# JWT 算法
ALGORITHM = "HS256"

# token 有效期（天）
TOKEN_EXPIRE_DAYS = 7

# 智谱 GLM 大模型 API Key（AI 库存管理员功能用）
# 获取方式：注册 https://open.bigmodel.cn → 右上角"API密钥" → 创建并复制
# 优先读环境变量 ZHIPU_API_KEY，没有就用下面引号里的值
ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", "")
