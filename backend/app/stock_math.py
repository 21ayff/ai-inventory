"""库存参数自动计算（改进版）

用户只需提供自己知道的经营信息：
- 日均销量（件/天）
- 平均到货时间（天）
- 当前库存（件）
- 商品分类（决定目标库存天数和服务水平 Z 值）
- 保质期天数（可选）

系统自动算出三个专业参数：
- 安全库存（min_stock）
- 订货点（rop）
- 建议补货量（eoq，语义上为「建议每次补多少」）

公式说明：
1. 提前期需求 = 日均销量 × 到货天数
2. 安全库存   = Z × 日销量标准差 × √到货天数
   - 第一阶段没有历史标准差时，用「日均销量 × 默认波动系数(20%)」估算
3. 订货点     = 提前期需求 + 安全库存
4. 目标库存   = 日均销量 × 分类目标库存天数
5. 保质期约束 = 日均销量 × 保质期天数 × 50%
6. 建议补货量 = max(目标库存 - 当前库存, EOQ)，取较大值确保达到经济订货量
"""

import math

# 默认日销量波动系数（20%），在没有历史销量标准差时使用
DEFAULT_DEMAND_CV = 0.20

# 默认分类策略
DEFAULT_TARGET_DAYS = 7.0   # 默认目标库存天数 7 天
DEFAULT_Z_SCORE = 1.65      # 默认 95% 服务水平

# 保质期安全比例：最多只进保质期一半的量
SHELF_LIFE_SAFE_RATIO = 0.5


def calc_stock_params(
    daily_sales: float,
    lead_time_days: float,
    current_stock: float = 0,
    category_target_days: float = DEFAULT_TARGET_DAYS,
    category_z_score: float = DEFAULT_Z_SCORE,
    shelf_life_days: float | None = None,
    sales_std: float | None = None,
    eoq: float = 0,
):
    """根据日均销量、到货天数、当前库存等信息，计算 (安全库存, 订货点, 建议补货量)

    参数：
        daily_sales: 日均销量（件/天）
        lead_time_days: 平均到货时间（天）
        current_stock: 当前库存（件），默认 0
        category_target_days: 分类目标库存天数，默认 7 天
        category_z_score: 分类服务水平 Z 值，默认 1.65（95%）
        shelf_life_days: 保质期天数，默认 None 表示不约束
        sales_std: 日销量标准差，默认 None 时用 20% 波动系数估算
        eoq: 经济订货量，默认 0 表示不应用 EOQ 约束

    日均销量 <= 0 时，三个参数都返回 0。
    """
    if not daily_sales or daily_sales <= 0:
        return 0.0, 0.0, 0.0

    # 1. 提前期需求
    lead_time_demand = daily_sales * lead_time_days

    # 2. 安全库存：Z × σ_d × √L
    # 没有历史标准差时，用日均销量的 20% 作为估算标准差
    if sales_std is not None and sales_std >= 0:
        sigma_d = sales_std
    else:
        sigma_d = daily_sales * DEFAULT_DEMAND_CV

    # 防止到货天数为 0 时数学错误
    effective_lead_time = max(lead_time_days, 0)
    safety_stock = category_z_score * sigma_d * math.sqrt(effective_lead_time)
    safety_stock = round(safety_stock, 2)

    # 3. 订货点
    reorder_point = round(lead_time_demand + safety_stock, 2)

    # 4. 目标库存
    target_inventory = daily_sales * category_target_days

    # 5. 保质期约束（如果填写了保质期）
    if shelf_life_days and shelf_life_days > 0:
        shelf_life_cap = daily_sales * shelf_life_days * SHELF_LIFE_SAFE_RATIO
        target_inventory = min(target_inventory, shelf_life_cap)

    # 6. 建议补货量 = max(目标库存 - 当前库存, EOQ)，取较大值确保达到经济订货量
    gap = max(target_inventory - current_stock, 0)
    if eoq and eoq > 0:
        suggest_qty = max(gap, eoq)
    else:
        suggest_qty = gap
    suggest_qty = round(suggest_qty, 2)

    return safety_stock, reorder_point, suggest_qty
