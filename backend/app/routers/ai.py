"""AI 功能接口（数据按账号隔离）

1. /api/ai/replenish  AI 补货提醒（规则计算，保留）
2. /api/ai/chat       AI 库存管理员对话（调用智谱 GLM 大模型）
3. /api/ai/history    查看对话历史 / 清空对话
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Category, Product, AiChatHistory, User
from ..schemas import ReplenishItem, ChatRequest, ChatResponse, ChatHistoryItem
from ..dependencies import get_current_user
from ..stock_math import calc_stock_params, DEFAULT_TARGET_DAYS, DEFAULT_Z_SCORE
from ..sales_stats import calc_sales_std, detect_sales_trend
from ..eoq import calc_eoq, get_order_cost, get_holding_cost_rate
from ..llm import chat as llm_chat, LLMError

router = APIRouter(prefix="/api/ai", tags=["ai"], dependencies=[Depends(get_current_user)])

# 发给大模型时最多携带的历史对话条数（一问一答算 1 条）
MAX_HISTORY_ROUNDS = 8

# 系统提示词里最多列出多少个商品（防止商品太多撑爆上下文）
MAX_PRODUCTS_IN_PROMPT = 60


def _category_strategy(db: Session, category_id: int | None, user_id: int):
    """读取分类的库存策略（只查当前账号的分类），未选择分类时返回默认值"""
    if category_id:
        cat = db.query(Category).filter(
            Category.id == category_id, Category.user_id == user_id
        ).first()
        if cat:
            return cat.target_days, cat.z_score
    return DEFAULT_TARGET_DAYS, DEFAULT_Z_SCORE


@router.get("/replenish", response_model=list[ReplenishItem])
def get_replenish_suggestions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """AI 补货提醒：扫描当前账号的商品，返回需要补货的商品及建议"""
    products = db.query(Product).filter(
        Product.deleted == False, Product.user_id == user.id
    ).all()
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
        target_days, z_score = _category_strategy(db, p.category_id, user.id)
        # 读取当前账号的订货成本和持有成本率，计算经济订货量 EOQ
        order_cost = get_order_cost(db, user.id)
        holding_cost_rate = get_holding_cost_rate(db, user.id)
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
            f"补货量 = min(目标库存 - 当前库存 + 提前期需求, EOQ)，"
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


# ---------- AI 库存管理员（大模型对话） ----------

def _build_inventory_context(db: Session, user_id: int) -> str:
    """把当前账号的实时库存数据整理成一段文字，塞进系统提示词

    AI 每次回答都基于这段最新数据，所以永远是实时情况。
    """
    products = db.query(Product).filter(
        Product.deleted == False, Product.user_id == user_id
    ).order_by(Product.id.asc()).all()

    total_count = len(products)
    if total_count == 0:
        return "【当前库存数据】\n暂无任何商品，用户可能刚注册还没录入数据。"

    total_stock_value = 0.0
    urgent, suggest, normal = [], [], []
    for p in products:
        cost = p.cost_price or 0
        total_stock_value += p.current_stock * cost
        if p.current_stock < p.min_stock:
            urgent.append(p)
        elif p.rop > 0 and p.current_stock < p.rop:
            suggest.append(p)
        else:
            normal.append(p)

    lines = [
        "【当前库存数据】（系统实时提供，AI 必须基于此数据分析，不得编造）",
        f"商品总数：{total_count} 种；库存总货值（按成本价）：{round(total_stock_value, 2)} 元",
        f"紧急缺货（低于安全库存）：{len(urgent)} 种；建议补货（低于订货点）：{len(suggest)} 种",
        "",
        "各商品明细（格式：名称 | 当前库存 | 安全库存 | 订货点 | 日均销量 | 成本价 | 单位 | 到货天数 | 供应商）：",
    ]

    def product_line(p: Product) -> str:
        cost = f"{p.cost_price}元" if p.cost_price is not None else "未填"
        supplier = p.supplier_name or "未填"
        return (
            f"{p.name} | {p.current_stock} | {p.min_stock} | {p.rop} | "
            f"{p.daily_sales} | {cost} | {p.unit} | {p.lead_time_days}天 | {supplier}"
        )

    # 优先列缺货和待补货的商品（用户最关心），正常商品靠后
    shown = urgent + suggest + normal
    for p in shown[:MAX_PRODUCTS_IN_PROMPT]:
        lines.append(product_line(p))
    if len(shown) > MAX_PRODUCTS_IN_PROMPT:
        lines.append(f"（其余 {len(shown) - MAX_PRODUCTS_IN_PROMPT} 种商品已省略）")

    return "\n".join(lines)


def _build_system_prompt(db: Session, user_id: int) -> str:
    """组装系统提示词：AI 人设 + 实时库存数据"""
    persona = (
        "你是「AI智能库存助手」系统里的常驻库存管理员，大家都叫你小库。"
        "你服务的对象是便利店、小超市的店主，他们不一定懂专业库存术语。\n\n"
        "你的职责：\n"
        "1. 用通俗接地气的中文，回答店主关于库存、补货、滞销、资金占用的各种问题\n"
        "2. 基于下方【当前库存数据】给出具体可执行的建议，直接点名具体商品和数量\n"
        "3. 需要时可以用简单的算式展示你的推理过程，让店主看得明白\n\n"
        "规则：\n"
        "- 只基于【当前库存数据】分析，数据里没有的（比如售价、利润）要如实说明暂无记录\n"
        "- 涉及补货可参考安全库存/订货点理论，但要用大白话解释\n"
        "- 回答控制在 300 字以内，重点突出，多用列表\n"
        "- 你只负责给建议，不能替店主做决定，重要决策提醒店主自行确认\n"
    )
    return persona + "\n" + _build_inventory_context(db, user_id)


@router.post("/chat", response_model=ChatResponse)
def ai_chat(data: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """AI 库存管理员对话：带上历史记录和实时库存数据调用大模型"""
    message = data.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")
    if len(message) > 500:
        raise HTTPException(status_code=400, detail="消息太长了，请控制在 500 字以内")

    # 1. 取最近几轮历史对话（按时间正序），让 AI 记得之前聊了什么
    history = (
        db.query(AiChatHistory)
        .filter(AiChatHistory.user_id == user.id)
        .order_by(AiChatHistory.id.desc())
        .limit(MAX_HISTORY_ROUNDS)
        .all()
    )
    history.reverse()

    # 2. 组装 OpenAI 格式消息列表：系统提示词 + 历史对话 + 本次提问
    messages = [{"role": "system", "content": _build_system_prompt(db, user.id)}]
    for h in history:
        messages.append({"role": "user", "content": h.question})
        messages.append({"role": "assistant", "content": h.answer})
    messages.append({"role": "user", "content": message})

    # 3. 调用大模型
    try:
        answer = llm_chat(messages)
    except LLMError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # 4. 保存一问一答到对话历史
    record = AiChatHistory(user_id=user.id, question=message, answer=answer)
    db.add(record)
    db.commit()

    return ChatResponse(answer=answer)


@router.get("/history", response_model=list[ChatHistoryItem])
def get_chat_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """当前账号的对话历史（最近 50 条，按时间正序返回）"""
    records = (
        db.query(AiChatHistory)
        .filter(AiChatHistory.user_id == user.id)
        .order_by(AiChatHistory.id.desc())
        .limit(50)
        .all()
    )
    records.reverse()
    return records


@router.delete("/history")
def clear_chat_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """清空当前账号的对话历史（只删自己的）"""
    deleted = (
        db.query(AiChatHistory)
        .filter(AiChatHistory.user_id == user.id)
        .delete()
    )
    db.commit()
    return {"message": f"已清空 {deleted} 条对话记录"}
