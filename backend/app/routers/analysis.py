"""数据分析接口

覆盖便利店日常经营的三个核心动作：
1. 今日生意：今天赚了多少钱（销售额、毛利、最好卖商品）
2. 该进货了：该进什么货（库存低于订货点的商品 + 预估总成本）
3. 钱压在哪：钱变成了什么货（总货值、最压钱 TOP3、滞销品清仓建议）
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product, StockRecord
from ..schemas import (
    AnalysisOverview,
    TodayBusiness,
    RestockItem,
    RestockList,
    StuckItem,
    MoneyStuck,
)
from ..dependencies import get_current_user
from ..stock_math import calc_stock_params
from ..eoq import calc_eoq, get_order_cost, get_holding_cost_rate

router = APIRouter(
    prefix="/api/analysis",
    tags=["analysis"],
    dependencies=[Depends(get_current_user)],
)

# 滞销判断阈值：多少天没出库算滞销
SLOW_MOVING_DAYS = 30
# 滞销品打折系数：清仓可回收 80% 成本
SLOW_MOVING_DISCOUNT = 0.8


def _today_range():
    """返回今天的起止时间 [00:00, 次日00:00)"""
    now = datetime.now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start, end


def _build_today(db: Session) -> TodayBusiness:
    """板块1：今日生意"""
    start, end = _today_range()

    # 今日出库记录
    records = (
        db.query(StockRecord)
        .filter(StockRecord.type == "out")
        .filter(StockRecord.created_at >= start)
        .filter(StockRecord.created_at < end)
        .all()
    )

    products = db.query(Product).filter(Product.deleted == False).all()
    product_map = {p.id: p for p in products}

    today_sales = 0.0       # 销售额（按成本价估算，因无售价字段）
    today_cost = 0.0       # 销售成本
    best_seller_name = None
    best_seller_qty = 0.0
    best_seller_unit = "个"
    qty_by_product = {}

    for r in records:
        qty = r.quantity or 0
        product = product_map.get(r.product_id)
        if not product:
            continue
        # 销售额按成本价的 1.3 倍估算售价（便利店常见毛利率约 23%）
        # 但这里没有售价字段，先用成本价计算货值，毛利先标记为 0
        # 改进：如果有售价字段，这里应该用售价
        cost_price = product.cost_price or 0
        # 售价按成本价的 1.3 倍估算（30% 毛利率）
        unit_price = cost_price * 1.3 if cost_price > 0 else 0
        today_sales += unit_price * qty
        today_cost += cost_price * qty

        qty_by_product[r.product_id] = qty_by_product.get(r.product_id, 0) + qty

    today_profit = round(today_sales - today_cost, 2)

    # 最好卖的商品
    if qty_by_product:
        best_pid = max(qty_by_product, key=qty_by_product.get)
        best_product = product_map.get(best_pid)
        if best_product:
            best_seller_name = best_product.name
            best_seller_qty = round(qty_by_product[best_pid], 2)
            best_seller_unit = best_product.unit or "个"

    return TodayBusiness(
        today_sales=round(today_sales, 2),
        today_profit=today_profit,
        best_seller_name=best_seller_name,
        best_seller_qty=best_seller_qty,
        best_seller_unit=best_seller_unit,
    )


def _build_restock(db: Session) -> RestockList:
    """板块2：该进货了（库存 < 订货点的商品）"""
    products = db.query(Product).filter(Product.deleted == False).all()

    order_cost = get_order_cost(db)
    holding_cost_rate = get_holding_cost_rate(db)

    items = []
    for p in products:
        # 低于订货点才提示进货
        if p.current_stock >= p.rop:
            continue
        # 实时计算建议补货量（复用 stock_math 的公式）
        eoq_value = calc_eoq(p.daily_sales, p.cost_price, order_cost, holding_cost_rate)
        _, _, suggest_qty = calc_stock_params(
            daily_sales=p.daily_sales,
            lead_time_days=p.lead_time_days,
            current_stock=p.current_stock,
            shelf_life_days=p.shelf_life_days,
            eoq=eoq_value,
        )
        if suggest_qty <= 0:
            continue
        # 预估进货成本
        cost = p.cost_price or 0
        total_cost = round(suggest_qty * cost, 2)
        items.append(RestockItem(
            product_id=p.id,
            name=p.name,
            unit=p.unit or "个",
            current_stock=p.current_stock,
            rop=p.rop,
            suggest_qty=suggest_qty,
            cost_price=p.cost_price,
            total_cost=total_cost,
            supplier_name=p.supplier_name,
            supplier_phone=p.supplier_phone,
        ))

    # 按建议成本从高到低排序
    items.sort(key=lambda x: x.total_cost, reverse=True)
    total = round(sum(i.total_cost for i in items), 2)
    return RestockList(count=len(items), items=items, total_cost=total)


def _build_money_stuck(db: Session) -> MoneyStuck:
    """板块3：钱压在哪"""
    products = db.query(Product).filter(Product.deleted == False).all()
    product_ids = [p.id for p in products]

    # 查找每个商品最后一次出库时间
    last_out_map = {}
    if product_ids:
        out_records = (
            db.query(StockRecord)
            .filter(StockRecord.type == "out")
            .filter(StockRecord.product_id.in_(product_ids))
            .order_by(StockRecord.product_id, StockRecord.created_at.desc())
            .all()
        )
        seen = set()
        for r in out_records:
            if r.product_id not in seen:
                last_out_map[r.product_id] = r.created_at
                seen.add(r.product_id)

    now = datetime.now()
    stuck_items = []
    slow_items = []
    total_stock_value = 0.0

    for p in products:
        cost = p.cost_price or 0
        stock_value = round(p.current_stock * cost, 2)
        total_stock_value += stock_value

        # 计算滞销天数
        last_out = last_out_map.get(p.id)
        if last_out:
            days_no_sale = (now - last_out).days
        else:
            # 从未出库，用创建时间起算
            days_no_sale = (now - p.created_at).days if p.created_at else None

        item = StuckItem(
            product_id=p.id,
            name=p.name,
            unit=p.unit or "个",
            current_stock=p.current_stock,
            cost_price=p.cost_price,
            stock_value=stock_value,
            days_no_sale=days_no_sale,
        )
        stuck_items.append(item)

        # 滞销品：超过阈值天数没出库且库存成本 > 0
        if days_no_sale is not None and days_no_sale >= SLOW_MOVING_DAYS and stock_value > 0:
            slow_items.append(item)

    # 最压钱 TOP3
    stuck_items.sort(key=lambda x: x.stock_value, reverse=True)
    top_items = stuck_items[:3]

    # 可释放资金 = 滞销品库存成本 × 0.8
    slow_value = sum(i.stock_value for i in slow_items)
    releasable = round(slow_value * SLOW_MOVING_DISCOUNT, 2)

    return MoneyStuck(
        total_stock_value=round(total_stock_value, 2),
        top_items=top_items,
        slow_moving=slow_items,
        releasable_amount=releasable,
    )


@router.get("/overview", response_model=AnalysisOverview)
def get_analysis_overview(db: Session = Depends(get_db)):
    """数据分析总览：今日生意 + 该进货了 + 钱压在哪"""
    today = _build_today(db)
    restock = _build_restock(db)
    money_stuck = _build_money_stuck(db)
    return AnalysisOverview(today=today, restock=restock, money_stuck=money_stuck)
