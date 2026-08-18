"""库存参数自动计算（AI 简化模型）

用户只需提供自己知道的经营信息：
- 日均销量（件/天）
- 平均到货时间（天）

系统自动算出三个专业参数：
- 安全库存（min_stock）
- 订货点（rop）
- 建议补货量（eoq，语义上为「建议每次补多少」，非严格 EOQ）

公式说明：
1. 提前期需求 = 日均销量 × 到货天数
2. 安全库存   = 提前期需求 × 安全系数
3. 订货点     = 提前期需求 + 安全库存
4. 建议补货量 = 日均销量 × 建议补货天数
"""

# 安全系数：第一阶段固定为 30%（正常商品）
# 后续可改为 AI 根据历史销量波动、实际到货时间等自动判断
SAFETY_FACTOR = 0.3

# 建议补货天数：每次建议补约一个月的用量
REORDER_PERIOD_DAYS = 30


def calc_stock_params(daily_sales: float, lead_time_days: float):
    """根据日均销量和到货天数，计算 (安全库存, 订货点, 建议补货量)

    日均销量 <= 0 时，三个参数都返回 0。
    """
    if not daily_sales or daily_sales <= 0:
        return 0.0, 0.0, 0.0

    lead_time_demand = daily_sales * lead_time_days          # 提前期需求
    safety_stock = round(lead_time_demand * SAFETY_FACTOR, 2)  # 安全库存
    reorder_point = round(lead_time_demand + safety_stock, 2)  # 订货点
    suggest_qty = round(daily_sales * REORDER_PERIOD_DAYS, 2)  # 建议补货量

    return safety_stock, reorder_point, suggest_qty
