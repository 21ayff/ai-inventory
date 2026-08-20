"""EOQ 经济订货量计算模块（第三阶段）

基于经典 EOQ 公式计算最优订货批量，避免频繁小批量订货或单次订货过多。

公式：
    Q = √(2 × D × S / H)
其中：
    D = 年需求量（日均销量 × 365）
    S = 每次订货成本（固定费用，如运费、人工费）
    H = 单位年持有成本（成本价 × 持有成本率）
"""
import math
from sqlalchemy.orm import Session

from .models import Setting

# 默认配置（当 Setting 表没有对应配置时使用）
DEFAULT_ORDER_COST = 20.0       # 默认每次订货成本 20 元（便利店单SKU分摊成本）
DEFAULT_HOLDING_COST_RATE = 0.25  # 默认年持有成本率 25%（年化）

# 年化天数：EOQ公式要求 D（年需求）和 H（年持有成本）时间单位必须一致
ANNUAL_DAYS = 365


def get_order_cost(db: Session, user_id: int) -> float:
    """从 Setting 表读取当前账号的每次订货成本，读取失败返回默认值"""
    setting = db.query(Setting).filter(
        Setting.key == "order_cost", Setting.user_id == user_id
    ).first()
    if setting:
        try:
            return float(setting.value)
        except (ValueError, TypeError):
            pass
    return DEFAULT_ORDER_COST


def get_holding_cost_rate(db: Session, user_id: int) -> float:
    """从 Setting 表读取当前账号的持有成本率，读取失败返回默认值"""
    setting = db.query(Setting).filter(
        Setting.key == "holding_cost_rate", Setting.user_id == user_id
    ).first()
    if setting:
        try:
            return float(setting.value)
        except (ValueError, TypeError):
            pass
    return DEFAULT_HOLDING_COST_RATE


def calc_eoq(
    daily_sales: float,
    cost_price: float | None,
    order_cost: float = DEFAULT_ORDER_COST,
    holding_cost_rate: float = DEFAULT_HOLDING_COST_RATE,
):
    """计算经济订货量 EOQ

    参数：
        daily_sales: 日均销量（件/天）
        cost_price: 单位成本价（元/件），None 时返回 0
        order_cost: 每次订货成本（元/次）
        holding_cost_rate: 持有成本率（如 0.25 表示 25%）

    返回：经济订货量 Q（件），四舍五入保留两位小数
    """
    if not daily_sales or daily_sales <= 0:
        return 0.0
    if cost_price is None or cost_price <= 0:
        return 0.0

    # 年需求量（日均销量 × 年化天数，与H保持同一时间单位）
    annual_demand = daily_sales * ANNUAL_DAYS

    # 单位年持有成本
    holding_cost_per_unit = cost_price * holding_cost_rate

    if holding_cost_per_unit <= 0:
        return 0.0

    # EOQ = √(2 × D × S / H)
    eoq = math.sqrt(2 * annual_demand * order_cost / holding_cost_per_unit)
    return round(eoq, 2)
