"""设置接口（第三阶段）

管理全局订货成本和持有成本率，用于 EOQ 计算。
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Setting
from ..schemas import SettingsOut, SettingsUpdate
from ..dependencies import get_current_user
from ..eoq import DEFAULT_ORDER_COST, DEFAULT_HOLDING_COST_RATE

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    """获取全局设置（订货成本和持有成本率）"""
    order_cost = DEFAULT_ORDER_COST
    holding_cost_rate = DEFAULT_HOLDING_COST_RATE

    oc_setting = db.query(Setting).filter(Setting.key == "order_cost").first()
    if oc_setting:
        try:
            order_cost = float(oc_setting.value)
        except (ValueError, TypeError):
            pass

    hcr_setting = db.query(Setting).filter(Setting.key == "holding_cost_rate").first()
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
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db)):
    """更新全局设置（订货成本和持有成本率）"""
    if data.order_cost is not None:
        if data.order_cost < 0:
            data.order_cost = 0
        setting = db.query(Setting).filter(Setting.key == "order_cost").first()
        if setting:
            setting.value = str(data.order_cost)
        else:
            db.add(Setting(key="order_cost", value=str(data.order_cost)))

    if data.holding_cost_rate is not None:
        if data.holding_cost_rate < 0:
            data.holding_cost_rate = 0
        if data.holding_cost_rate > 1:
            data.holding_cost_rate = 1
        setting = db.query(Setting).filter(Setting.key == "holding_cost_rate").first()
        if setting:
            setting.value = str(data.holding_cost_rate)
        else:
            db.add(Setting(key="holding_cost_rate", value=str(data.holding_cost_rate)))

    db.commit()

    # 返回更新后的值
    return get_settings(db)
