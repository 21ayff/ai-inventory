"""历史销量统计模块（第二阶段 + 第三阶段）

第二阶段：从 StockRecord 出库记录中按日聚合销量，计算日销量标准差。
当历史数据不足时返回 None，由调用方回退到估算值（日均销量 × 20%）。

第三阶段：新增日均销量计算和销量趋势判断，用于动态预测。
"""
from datetime import datetime, timedelta
import statistics
from sqlalchemy.orm import Session

from .models import StockRecord

# 最少有效天数：有出库记录的天数达到此值才计算真实标准差
MIN_HISTORY_DAYS = 7

# 默认统计周期（天）
DEFAULT_STATS_DAYS = 30

# 销量趋势判断阈值：差异超过 30% 视为趋势变化
SALES_TREND_THRESHOLD = 0.30


def calc_sales_std(db: Session, product_id: int, stats_days: int = DEFAULT_STATS_DAYS):
    """计算商品最近 stats_days 天的日销量标准差

    参数：
        db: 数据库会话
        product_id: 商品 ID
        stats_days: 统计周期（天），默认 30

    返回：(标准差, 有效天数, 日销量列表)
        - 标准差为 None 表示数据不足，需回退到估算
        - 有效天数 = 有出库记录的天数（用于判断是否回退）
        - 日销量列表 = 统计周期内每一天的销量（无出库算 0，用于计算标准差）
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=stats_days)

    # 读取统计周期内的出库记录
    records = db.query(StockRecord).filter(
        StockRecord.product_id == product_id,
        StockRecord.type == "out",
        StockRecord.created_at >= start_date,
        StockRecord.created_at <= end_date,
    ).all()

    # 按日聚合出库量
    daily_sales_map = {}
    for r in records:
        day_key = r.created_at.date()
        daily_sales_map[day_key] = daily_sales_map.get(day_key, 0) + r.quantity

    # 有效天数 = 有出库记录的天数
    active_days = len(daily_sales_map)

    # 数据不足时返回 None，由调用方回退到估算
    if active_days < MIN_HISTORY_DAYS:
        return None, active_days, []

    # 构建日销量列表（统计周期内每一天，无出库算 0）
    sales_list = []
    current = start_date.date()
    end = end_date.date()
    while current <= end:
        sales_list.append(daily_sales_map.get(current, 0))
        current += timedelta(days=1)

    # 样本标准差（除以 n-1），适合用样本估算总体波动
    if len(sales_list) < 2:
        return None, active_days, sales_list

    std = statistics.stdev(sales_list)
    return round(std, 2), active_days, sales_list


def calc_recent_daily_sales(db: Session, product_id: int, recent_days: int = 14):
    """计算商品最近 recent_days 天的实际日均销量（用于动态预测）

    参数：
        db: 数据库会话
        product_id: 商品 ID
        recent_days: 统计周期（天），默认 14

    返回：(日均销量, 有效天数)
        - 日均销量 = 统计周期内总出库量 / 统计天数
        - 有效天数 = 统计天数（含无出库天数，用于判断数据可靠性）
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=recent_days)

    records = db.query(StockRecord).filter(
        StockRecord.product_id == product_id,
        StockRecord.type == "out",
        StockRecord.created_at >= start_date,
        StockRecord.created_at <= end_date,
    ).all()

    total_sales = sum(r.quantity for r in records)
    avg_daily = total_sales / recent_days if recent_days > 0 else 0
    return round(avg_daily, 2), recent_days


def detect_sales_trend(
    db: Session,
    product_id: int,
    user_daily_sales: float,
    recent_days: int = 14,
):
    """检测销量趋势：对比用户填写的日均销量与近期实际销量

    参数：
        db: 数据库会话
        product_id: 商品 ID
        user_daily_sales: 用户填写的日均销量
        recent_days: 统计周期（天），默认 14

    返回：(趋势描述, 实际日均销量, 差异率)
        - 趋势描述：稳定 / 上升 / 下降 / 数据不足
        - 实际日均销量：最近 N 天的日均销量
        - 差异率：实际销量相对于用户填写值的偏差比例
    """
    actual_daily, _ = calc_recent_daily_sales(db, product_id, recent_days)

    # 数据不足判断（总出库量为 0 视为数据不足）
    if actual_daily <= 0:
        return "数据不足", actual_daily, 0.0

    # 计算差异率
    if user_daily_sales <= 0:
        return "上升", actual_daily, 1.0  # 用户填写 0 但有实际销量

    diff_rate = (actual_daily - user_daily_sales) / user_daily_sales

    # 趋势判断
    if abs(diff_rate) <= SALES_TREND_THRESHOLD:
        trend = "稳定"
    elif diff_rate > 0:
        trend = "上升"
    else:
        trend = "下降"

    return trend, actual_daily, round(diff_rate, 2)

