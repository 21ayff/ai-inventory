"""设置接口（第三阶段，按账号隔离）

管理每个账号自己的订货成本和持有成本率，用于 EOQ 计算。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Setting, User
from ..schemas import SettingsOut, SettingsUpdate
from ..dependencies import get_current_user
from ..eoq import DEFAULT_ORDER_COST, DEFAULT_HOLDING_COST_RATE

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """获取当前账号的设置（订货成本和持有成本率）"""
    order_cost = DEFAULT_ORDER_COST
    holding_cost_rate = DEFAULT_HOLDING_COST_RATE

    oc_setting = db.query(Setting).filter(
        Setting.key == "order_cost", Setting.user_id == user.id
    ).first()
    if oc_setting:
        try:
            order_cost = float(oc_setting.value)
        except (ValueError, TypeError):
            pass

    hcr_setting = db.query(Setting).filter(
        Setting.key == "holding_cost_rate", Setting.user_id == user.id
    ).first()
    if hcr_setting:
        try:
            holding_cost_rate = float(hcr_setting.value)
        except (ValueError, TypeError):
            pass

    return SettingsOut(
        order_cost=order_cost,
        holding_cost_rate=holding_cost_rate,
    )


@router.put("", response_model=SettingsOut)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """更新当前账号的设置（订货成本和持有成本率）"""
    if data.order_cost is not None:
        if data.order_cost < 0:
            data.order_cost = 0
        setting = db.query(Setting).filter(
            Setting.key == "order_cost", Setting.user_id == user.id
        ).first()
        if setting:
            setting.value = str(data.order_cost)
        else:
            db.add(Setting(user_id=user.id, key="order_cost", value=str(data.order_cost)))

    if data.holding_cost_rate is not None:
        if data.holding_cost_rate < 0:
            data.holding_cost_rate = 0
        if data.holding_cost_rate > 1:
            data.holding_cost_rate = 1
        setting = db.query(Setting).filter(
            Setting.key == "holding_cost_rate", Setting.user_id == user.id
        ).first()
        if setting:
            setting.value = str(data.holding_cost_rate)
        else:
            db.add(Setting(user_id=user.id, key="holding_cost_rate", value=str(data.holding_cost_rate)))

    db.commit()

    # 返回更新后的值
    return get_settings(db, user)
