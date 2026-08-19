"""AI 功能接口"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Product
from ..schemas import ReplenishItem, AskRequest, AskResponse
from ..dependencies import get_current_user
from ..stock_math import calc_stock_params, DEFAULT_TARGET_DAYS, DEFAULT_Z_SCORE
from ..sales_stats import calc_sales_std, detect_sales_trend
from ..eoq import calc_eoq, get_order_cost, get_holding_cost_rate

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(get_current_user)])


def _category_strategy(db: Session, category_id: int | None):
    """读取分类的库存策略，未选择分类时返回默认值"""
    if category_id:
        cat = db.query(Category).filter(Category.id == category_id).first()
        if cat:
            return cat.target_days, cat.z_score
    return DEFAULT_TARGET_DAYS, DEFAULT_Z_SCORE


@router.get("/replenish", response_model=list[ReplenishItem])
def get_replenish_suggestions(db: Session = Depends(get_db)):
    """AI 补货提醒：扫描所有商品，返回需要补货的商品及建议"""
    products = db.query(Product).filter(Product.deleted == False).all()
    suggestions = []

    for p in products:
        # 判断补货状态
        if p.current_stock < p.min_stock:
            status = "urgent"
        elif p.rop > 0 and p.current_stock < p.rop:
            status = "suggest"
        else:
            continue

        # 实时用新公式计算建议补货量，不直接使用数据库里的 p.eoq
        target_days, z_score = _category_strategy(db, p.category_id)
        # 读取全局订货成本和持有成本率，计算经济订货量 EOQ
        order_cost = get_order_cost(db)
        holding_cost_rate = get_holding_cost_rate(db)
        eoq_value = calc_eoq(p.daily_sales, p.cost_price, order_cost, holding_cost_rate)
        # 查询历史销量标准差（数据不足时返回 None，自动回退到估算）
        sales_std, active_days, _ = calc_sales_std(db, p.id)
        # 查询销量趋势（动态预测）
        trend, actual_daily, diff_rate = detect_sales_trend(db, p.id, p.daily_sales)
        _, _, suggest_qty = calc_stock_params(
            daily_sales=p.daily_sales,
            lead_time_days=p.lead_time_days,
            current_stock=p.current_stock,
            category_target_days=target_days,
            category_z_score=z_score,
            shelf_life_days=p.shelf_life_days,
            sales_std=sales_std,
            eoq=eoq_value,
        )
        # 标注标准差来源：历史数据 or 估算
        std_source = (
            f"历史 {active_days} 天出库记录算得标准差 {sales_std}"
            if sales_std is not None
            else f"历史数据不足（{active_days} 天），用日均销量 × 20% 估算"
        )
        # EOQ 计算说明
        eoq_desc = ""
        if eoq_value > 0:
            eoq_desc = (
                f"；EOQ 经济订货量 = √(2 × 年需求 × 订货成本 / 持有成本) "
                f"= √(2 × {p.daily_sales * 365} × {order_cost} / {p.cost_price * holding_cost_rate}) ≈ {eoq_value}"
            )
        # 销量趋势提示
        trend_desc = ""
        if trend == "上升":
            trend_desc = f"；销量趋势提示：近期实际日均销量 {actual_daily}，高于填写值 {p.daily_sales}，建议更新"
        elif trend == "下降":
            trend_desc = f"；销量趋势提示：近期实际日均销量 {actual_daily}，低于填写值 {p.daily_sales}，建议更新"
        calc = (
            f"补货量 = max(目标库存 - 当前库存, EOQ)，"
            f"其中目标库存 = 日均销量 × {target_days}天"
            + (f"，并受保质期约束" if p.shelf_life_days else "")
            + f"，标准差来源：{std_source}"
            + eoq_desc
            + trend_desc
            + f"，最终建议补货 {suggest_qty} {p.unit}"
        )

        # 三段解释
        if status == "urgent":
            data_basis = (
                f"当前库存 {p.current_stock} {p.unit}，已低于安全库存 "
                f"{p.min_stock} {p.unit}，存在断货风险"
            )
        else:
            data_basis = (
                f"当前库存 {p.current_stock} {p.unit}，低于订货点 "
                f"{p.rop} {p.unit}，建议安排补货"
            )

        theory_basis = (
            "依据「安全库存理论」，库存不应低于安全库存线；"
            "依据「ROP订货点理论」，当库存低于订货点时需及时补货"
        )

        after = p.current_stock + suggest_qty

        suggestions.append(
            ReplenishItem(
                product_id=p.id,
                product_name=p.name,
                unit=p.unit,
                current_stock=p.current_stock,
                min_stock=p.min_stock,
                rop=p.rop,
                eoq=p.eoq,
                status=status,
                suggest_quantity=suggest_qty,
                data_basis=data_basis,
                theory_basis=theory_basis,
                calc_process=f"{calc}；补货后库存 = {after} {p.unit}",
            )
        )

    return suggestions


@router.post("/ask", response_model=AskResponse)
def ask(data: AskRequest, db: Session = Depends(get_db)):
    """AI 库存问答（规则匹配）"""
    question = data.question.strip()
    all_products = db.query(Product).filter(Product.deleted == False).all()

    # 1. 先看是否提到某个具体商品
    target = None
    for p in all_products:
        if p.name and p.name in question:
            target = p
            break

    if target:
        status = "充足"
        if target.current_stock < target.min_stock:
            status = f"库存不足（低于安全库存 {target.min_stock} {target.unit}）"
        elif target.rop > 0 and target.current_stock < target.rop:
            status = f"偏低（低于订货点 {target.rop} {target.unit}）"
        return AskResponse(
            answer=f"{target.name} 当前库存 {target.current_stock} {target.unit}，{status}。"
        )

    # 2. 缺货 / 库存不足
    if any(k in question for k in ["缺货", "库存不足", "快没了", "不够", "低库存"]):
        low = [p for p in all_products if p.current_stock < p.min_stock]
        if not low:
            return AskResponse(answer="目前没有库存不足的商品，库存都充足。")
        lines = [
            f"{i + 1}. {p.name}：库存 {p.current_stock} {p.unit}（低于安全库存 {p.min_stock} {p.unit}）"
            for i, p in enumerate(low)
        ]
        return AskResponse(answer="以下商品库存不足：\n" + "\n".join(lines))

    # 3. 补货
    if "补货" in question:
        need = [
            p for p in all_products
            if p.current_stock < p.min_stock or (p.rop > 0 and p.current_stock < p.rop)
        ]
        if not need:
            return AskResponse(answer="目前没有需要补货的商品。")
        lines = [f"{i + 1}. {p.name}：库存 {p.current_stock} {p.unit}" for i, p in enumerate(need)]
        return AskResponse(answer="以下商品需要补货：\n" + "\n".join(lines))

    # 4. 库存总量
    if any(k in question for k in ["总量", "总共", "一共", "总计", "总数"]):
        total = db.query(func.sum(Product.current_stock)).filter(
            Product.deleted == False
        ).scalar() or 0
        return AskResponse(answer=f"当前所有商品的库存总量为 {total}。")

    # 5. 商品数量
    if any(k in question for k in ["多少商品", "几个商品", "商品数", "几种", "多少个", "多少种"]):
        return AskResponse(answer=f"当前共有 {len(all_products)} 种商品。")

    # 默认帮助
    return AskResponse(
        answer=(
            "我可以帮你查询：\n"
            "1. 哪些商品缺货 / 库存不足\n"
            "2. 某个商品的库存（直接说商品名）\n"
            "3. 库存总量\n"
            "4. 有多少种商品\n"
            "5. 哪些商品需要补货"
        )
    )
