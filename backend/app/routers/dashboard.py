"""首页仪表盘统计接口"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product, StockRecord
from .ai import get_replenish_suggestions
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)])


def _date_str(dt):
    """把时间统一转成 YYYY-MM-DD 字符串（兼容 datetime 和字符串类型）"""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt[:10]
    return dt.strftime("%Y-%m-%d")


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    """返回首页仪表盘所需的统计数据和图表数据"""
    products = db.query(Product).filter(Product.deleted == False).all()

    # 1. 统计总览
    product_count = len(products)
    total_stock = sum(p.current_stock or 0 for p in products)
    # 低于安全库存 = 紧急补货
    urgent_count = sum(1 for p in products if p.current_stock < p.min_stock)
    # 库存 >= 安全库存，但低于订货点 = 建议补货
    suggest_count = sum(
        1
        for p in products
        if p.rop > 0 and p.min_stock <= p.current_stock < p.rop
    )
    replenish_count = urgent_count + suggest_count

    # 2. 库存分布（柱状图）：按当前库存从高到低取前 10 个
    distribution = sorted(
        [{"name": p.name, "value": p.current_stock or 0} for p in products],
        key=lambda x: x["value"],
        reverse=True,
    )[:10]

    # 3. 出入库趋势（折线图）：最近 7 天每天入库/出库总量
    records = (
        db.query(StockRecord)
        .order_by(StockRecord.id.desc())
        .limit(500)
        .all()
    )
    daily = {}
    for r in records:
        day = _date_str(r.created_at)
        if day is None:
            continue
        if day not in daily:
            daily[day] = {"in": 0, "out": 0}
        if r.type == "in":
            daily[day]["in"] += r.quantity or 0
        elif r.type == "out":
            daily[day]["out"] += r.quantity or 0

    # 补全最近 7 天的日期，保证折线图连续
    trend = []
    for i in range(6, -1, -1):
        day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append(
            {
                "date": day[5:],  # 只保留 MM-DD，显示更简洁
                "in": round(daily.get(day, {}).get("in", 0), 2),
                "out": round(daily.get(day, {}).get("out", 0), 2),
            }
        )

    # 4. 补货告警列表（复用 AI 补货提醒逻辑）
    suggestions = get_replenish_suggestions(db)
    replenish_list = [
        {
            "product_name": s.product_name,
            "status": s.status,
            "current_stock": s.current_stock,
            "suggest_quantity": s.suggest_quantity,
            "unit": s.unit,
        }
        for s in suggestions
    ]

    return {
        "product_count": product_count,
        "total_stock": round(total_stock, 2),
        "urgent_count": urgent_count,
        "suggest_count": suggest_count,
        "replenish_count": replenish_count,
        "stock_distribution": distribution,
        "stock_trend": trend,
        "replenish_list": replenish_list,
    }
