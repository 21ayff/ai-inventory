"""数据库模型（表结构）"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text

from .database import Base


def now():
    """统一使用本地当前时间（与图表统计的时间保持一致）"""
    return datetime.now()


class User(Base):
    """用户表"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=now)


class Category(Base):
    """分类表"""
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)


class Product(Base):
    """商品表"""
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, unique=True, index=True, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    image = Column(String, nullable=True)
    unit = Column(String, default="个")
    current_stock = Column(Float, default=0)
    daily_sales = Column(Float, default=0)      # 日均销量（件/天），由用户填写或后续 AI 自动统计
    lead_time_days = Column(Float, default=0)   # 平均到货时间（天），由用户填写
    min_stock = Column(Float, default=0)        # 安全库存（AI 自动计算）
    rop = Column(Float, default=0)              # 订货点（AI 自动计算）
    eoq = Column(Float, default=0)              # 建议补货量（AI 自动计算，非严格 EOQ）
    has_expiry = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=now)
    updated_at = Column(DateTime, default=now, onupdate=now)


class StockRecord(Base):
    """库存记录表（入库/出库/调整/盘点）"""
    __tablename__ = "stock_records"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    type = Column(String, nullable=False)  # in / out / adjust / check
    quantity = Column(Float, nullable=False)
    before_stock = Column(Float, default=0)
    after_stock = Column(Float, default=0)
    remark = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)


class OperationLog(Base):
    """操作日志表"""
    __tablename__ = "operation_logs"
    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    target_type = Column(String, nullable=True)
    target_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    operator = Column(String, nullable=True)
    created_at = Column(DateTime, default=now)


class AiSuggestion(Base):
    """AI建议表"""
    __tablename__ = "ai_suggestions"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    type = Column(String, nullable=True)  # 补货 / 异常
    content = Column(Text, nullable=True)
    data_basis = Column(Text, nullable=True)    # 数据依据
    theory_basis = Column(Text, nullable=True)  # 理论依据
    calc_process = Column(Text, nullable=True)  # 计算过程
    status = Column(String, default="未读")
    created_at = Column(DateTime, default=now)


class AiChatHistory(Base):
    """AI问答记录表"""
    __tablename__ = "ai_chat_history"
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime, default=now)


class Setting(Base):
    """设置表"""
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=True)
