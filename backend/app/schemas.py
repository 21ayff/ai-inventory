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


# ---------- 分类 ----------

class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    parent_id: int | None = None
    target_days: float = 7.0
    z_score: float = 1.65


# ---------- 商品 ----------

class ProductCreate(BaseModel):
    name: str
    sku: str | None = None
    category_id: int | None = None
    unit: str = "个"
    current_stock: float = 0
    daily_sales: float = 0        # 日均销量（件/天）
    lead_time_days: float = 0     # 平均到货时间（天）
    shelf_life_days: float | None = None  # 保质期天数，可空
    cost_price: float | None = None       # 成本价，可空
    supplier_name: str | None = None      # 供应商名称，可空
    supplier_phone: str | None = None     # 供应商电话，可空
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
    shelf_life_days: float | None = None
    cost_price: float | None = None
    supplier_name: str | None = None
    supplier_phone: str | None = None
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
    shelf_life_days: float | None = None
    cost_price: float | None = None
    supplier_name: str | None = None
    supplier_phone: str | None = None
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


# ---------- 设置 ----------

class SettingsOut(BaseModel):
    """订货成本和持有成本率（全局配置）"""
    order_cost: float = 50.0          # 每次订货成本（元/次）
    holding_cost_rate: float = 0.25   # 持有成本率（如 0.25 表示 25%）


class SettingsUpdate(BaseModel):
    order_cost: float | None = None
    holding_cost_rate: float | None = None


# ---------- 数据分析 ----------

class TodayBusiness(BaseModel):
    """板块1：今日生意"""
    today_sales: float = 0          # 今日销售额
    today_profit: float = 0         # 今日毛利
    best_seller_name: str | None = None  # 今日最好卖的商品名
    best_seller_qty: float = 0       # 最好卖商品的销量
    best_seller_unit: str = "个"


class RestockItem(BaseModel):
    """该进货了清单项"""
    product_id: int
    name: str
    unit: str
    current_stock: float
    rop: float
    suggest_qty: float               # 建议进货数量
    cost_price: float | None = None
    total_cost: float = 0           # 预估进货成本 = 建议数量 × 进价
    supplier_name: str | None = None
    supplier_phone: str | None = None


class RestockList(BaseModel):
    """板块2：该进货了"""
    count: int = 0
    items: list[RestockItem] = []
    total_cost: float = 0           # 预估总成本


class StuckItem(BaseModel):
    """钱压在哪 TOP 项"""
    product_id: int
    name: str
    unit: str
    current_stock: float
    cost_price: float | None = None
    stock_value: float = 0          # 库存成本 = 库存数量 × 进价
    days_no_sale: int | None = None  # 滞销天数（多少天没出库）


class MoneyStuck(BaseModel):
    """板块3：钱压在哪"""
    total_stock_value: float = 0    # 总货值
    top_items: list[StuckItem] = []  # 最压钱 TOP3
    slow_moving: list[StuckItem] = []  # 滞销品清单
    releasable_amount: float = 0    # 可释放资金 = 滞销品库存成本 × 0.8


class AnalysisOverview(BaseModel):
    """数据分析总览（3 个板块合并）"""
    today: TodayBusiness
    restock: RestockList
    money_stuck: MoneyStuck
