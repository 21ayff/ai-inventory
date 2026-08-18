"""统计分析接口"""
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product, StockRecord
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"], dependencies=[Depends(get_current_user)])


def _parse_time(dt):
    """把时间统一转成 datetime 对象（兼容 datetime 和字符串）"""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt
    try:
        return datetime.fromisoformat(dt)
    except ValueError:
        return datetime.strptime(dt[:19], "%Y-%m-%dT%H:%M:%S")


def _time_key(dt, range_type):
    """按时间维度生成分组 key 和显示 label"""
    d = _parse_time(dt)
    if d is None:
        return "未知", "未知"
    if range_type == "week":
        iso = d.isocalendar()
        return f"{iso[0]}-W{iso[1]:02d}", f"第{iso[1]}周"
    if range_type == "month":
        return d.strftime("%Y-%m"), d.strftime("%Y-%m")
    # 默认按天
    return d.strftime("%Y-%m-%d"), d.strftime("%m-%d")


@router.get("/overview")
def get_overview(range: str = "day", db: Session = Depends(get_db)):
    """统计分析总览，range 支持 day / week / month"""
    records = db.query(StockRecord).order_by(StockRecord.id.asc()).all()
    products = db.query(Product).filter(Product.deleted == False).all()
    name_map = {p.id: p.name for p in products}

    # 1. 统计汇总
    total_in = 0.0
    total_out = 0.0
    in_count = 0
    out_count = 0

    # 2. 各商品出入库聚合（用于排行和周转）
    in_by_product = defaultdict(float)
    out_by_product = defaultdict(float)

    # 3. 趋势聚合
    buckets = {}

    for r in records:
        qty = r.quantity or 0
        if r.type == "in":
            total_in += qty
            in_count += 1
            in_by_product[r.product_id] += qty
        elif r.type == "out":
            total_out += qty
            out_count += 1
            out_by_product[r.product_id] += qty

        key, label = _time_key(r.created_at, range)
        if key not in buckets:
            buckets[key] = {"label": label, "in": 0.0, "out": 0.0}
        if r.type == "in":
            buckets[key]["in"] += qty
        elif r.type == "out":
            buckets[key]["out"] += qty

    # 趋势：按时间 key 排序
    trend = []
    for key in sorted(buckets.keys()):
        b = buckets[key]
        trend.append(
            {"label": b["label"], "in": round(b["in"], 2), "out": round(b["out"], 2)}
        )

    # 出入库排行：入库最多 TOP10、出库最多 TOP10
    def build_rank(agg):
        items = [
            {"name": name_map.get(pid, f"商品{pid}"), "value": round(v, 2)}
            for pid, v in agg.items()
        ]
        items.sort(key=lambda x: x["value"], reverse=True)
        return items[:10]

    in_rank = build_rank(in_by_product)
    out_rank = build_rank(out_by_product)

    # 库存周转分析：周转率 = 出库总量 / 当前库存，周转天数按 30 天周期估算
    turnover = []
    for p in products:
        out_qty = out_by_product.get(p.id, 0)
        if out_qty > 0 and p.current_stock > 0:
            rate = round(out_qty / p.current_stock, 2)
            days = round(30 / rate, 1)
        else:
            rate = 0
            days = None
        turnover.append(
            {
                "name": p.name,
                "out_qty": round(out_qty, 2),
                "current_stock": p.current_stock,
                "rate": rate,
                "days": days,
            }
        )
    # 按周转率从高到低排序
    turnover.sort(key=lambda x: x["rate"], reverse=True)

    return {
        "total_in": round(total_in, 2),
        "total_out": round(total_out, 2),
        "in_count": in_count,
        "out_count": out_count,
        "trend": trend,
        "in_rank": in_rank,
        "out_rank": out_rank,
        "turnover": turnover,
    }
