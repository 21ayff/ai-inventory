"""库存记录接口（入库/出库，数据按账号隔离）"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Product, StockRecord, User
from ..schemas import StockRecordCreate, StockRecordOut
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/stock", tags=["stock"], dependencies=[Depends(get_current_user)])


@router.post("/records", response_model=StockRecordOut)
def create_record(data: StockRecordCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """入库或出库，并同步更新商品库存（只能操作当前账号的商品）"""
    product = db.query(Product).filter(
        Product.id == data.product_id,
        Product.user_id == user.id,
        Product.deleted == False,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="数量必须大于 0")

    before = product.current_stock

    if data.type == "in":
        after = before + data.quantity
    elif data.type == "out":
        if data.quantity > before:
            raise HTTPException(status_code=400, detail=f"库存不足，当前库存为 {before}")
        after = before - data.quantity
    else:
        raise HTTPException(status_code=400, detail="类型错误，只能是 in 或 out")

    product.current_stock = after

    record = StockRecord(
        user_id=user.id,
        product_id=data.product_id,
        type=data.type,
        quantity=data.quantity,
        before_stock=before,
        after_stock=after,
        remark=data.remark,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/records", response_model=list[StockRecordOut])
def list_records(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """最近的库存操作记录（只返回当前账号的）"""
    return (
        db.query(StockRecord)
        .filter(StockRecord.user_id == user.id)
        .order_by(StockRecord.id.desc())
        .limit(100)
        .all()
    )
