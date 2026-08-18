"""接口的请求/响应数据模型"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class ChangePasswordRequest(BaseModel):
    username: str
    old_password: str
    new_password: str


# ---------- 商品 ----------

class ProductCreate(BaseModel):
    name: str
    sku: str | None = None
    category_id: int | None = None
    unit: str = "个"
    current_stock: float = 0
    daily_sales: float = 0        # 日均销量（件/天）
    lead_time_days: float = 0     # 平均到货时间（天）
    min_stock: float = 0          # 安全库存（后端自动计算，可忽略）
    rop: float = 0                # 订货点（后端自动计算，可忽略）
    eoq: float = 0                # 建议补货量（后端自动计算，可忽略）


class ProductUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    category_id: int | None = None
    unit: str | None = None
    current_stock: float | None = None
    daily_sales: float | None = None
    lead_time_days: float | None = None
    min_stock: float | None = None
    rop: float | None = None
    eoq: float | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str | None = None
    category_id: int | None = None
    unit: str = "个"
    current_stock: float = 0
    daily_sales: float = 0
    lead_time_days: float = 0
    min_stock: float = 0
    rop: float = 0
    eoq: float = 0
    deleted: bool = False
    created_at: datetime | None = None


# ---------- 库存记录 ----------

class StockRecordCreate(BaseModel):
    product_id: int
    type: str  # "in" 入库 / "out" 出库
    quantity: float
    remark: str | None = None


class StockRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    type: str
    quantity: float
    before_stock: float
    after_stock: float
    remark: str | None = None
    created_at: datetime | None = None


# ---------- AI 补货提醒 ----------

class ReplenishItem(BaseModel):
    product_id: int
    product_name: str
    unit: str
    current_stock: float
    min_stock: float
    rop: float
    eoq: float
    status: str  # urgent 紧急 / suggest 建议
    suggest_quantity: float
    data_basis: str
    theory_basis: str
    calc_process: str


# ---------- AI 问答 ----------

class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
