"""AI 功能接口"""
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product
from ..schemas import ReplenishItem, AskRequest, AskResponse
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(get_current_user)])


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

        # 计算建议补货量
        if p.eoq and p.eoq > 0:
            suggest_qty = p.eoq
            calc = f"补货量 = AI建议补货量 = {p.eoq} {p.unit}"
        else:
            suggest_qty = max(p.rop + p.min_stock - p.current_stock, 0)
            calc = (
                f"补货量 = 订货点 + 安全库存 - 当前库存 = "
                f"{p.rop} + {p.min_stock} - {p.current_stock} = {suggest_qty} {p.unit}"
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
