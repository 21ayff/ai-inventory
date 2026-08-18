"""商品管理接口"""
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session
from openpyxl import Workbook, load_workbook

from ..database import get_db
from ..models import Product
from ..schemas import ProductCreate, ProductUpdate, ProductOut
from ..dependencies import get_current_user
from ..stock_math import calc_stock_params

router = APIRouter(prefix="/api/products", tags=["products"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ProductOut])
def list_products(
    search: str = "",
    stock_filter: str = "",
    db: Session = Depends(get_db),
):
    """商品列表，支持搜索和库存筛选"""
    query = db.query(Product).filter(Product.deleted == False)

    if search:
        query = query.filter(
            or_(Product.name.contains(search), Product.sku.contains(search))
        )

    if stock_filter == "low":      # 库存不足
        query = query.filter(Product.current_stock < Product.min_stock)

    return query.order_by(Product.id.desc()).all()


@router.post("", response_model=ProductOut)
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    """新增商品（安全库存/订货点/建议补货量由 AI 自动计算）"""
    if not data.name:
        raise HTTPException(status_code=400, detail="商品名称不能为空")

    if data.sku:
        exists = db.query(Product).filter(
            Product.sku == data.sku, Product.deleted == False
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="SKU 已存在")

    # 根据日均销量和到货天数自动计算三个专业参数
    min_stock, rop, eoq = calc_stock_params(data.daily_sales, data.lead_time_days)

    product = Product(
        name=data.name,
        sku=data.sku,
        category_id=data.category_id,
        unit=data.unit,
        current_stock=data.current_stock,
        daily_sales=data.daily_sales,
        lead_time_days=data.lead_time_days,
        min_stock=min_stock,
        rop=rop,
        eoq=eoq,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/import-template")
def download_import_template():
    """下载 Excel 导入模板"""
    wb = Workbook()
    ws = wb.active
    ws.title = "商品导入模板"
    ws.append(["商品名称", "SKU", "单位", "当前库存", "日均销量", "平均到货天数"])
    ws.append(["示例商品", "SKU001", "个", 100, 10, 7])

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=import_template.xlsx"},
    )


@router.post("/import")
async def import_products(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """从 Excel 批量导入商品，按名称覆盖更新已有商品"""
    content = await file.read()
    try:
        wb = load_workbook(BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="无法读取 Excel 文件，请使用 .xlsx 格式")

    ws = wb.active
    rows = list(ws.iter_rows(min_row=2, values_only=True))  # 跳过表头

    def parse_number(v):
        """解析数值：空值返回 0，非法值返回 None"""
        if v is None:
            return 0.0
        s = str(v).strip()
        if s == "":
            return 0.0
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    success = 0
    failed = []

    for i, row in enumerate(rows, start=2):
        # 跳过完全空的行
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue

        name = str(row[0]).strip() if len(row) > 0 and row[0] else ""
        sku = str(row[1]).strip() if len(row) > 1 and row[1] else None
        unit = str(row[2]).strip() if len(row) > 2 and row[2] else "个"
        current_stock = parse_number(row[3] if len(row) > 3 else None)
        daily_sales = parse_number(row[4] if len(row) > 4 else None)
        lead_time_days = parse_number(row[5] if len(row) > 5 else None)

        if not name:
            failed.append(f"第{i}行：商品名称为空")
            continue

        if any(v is None for v in [current_stock, daily_sales, lead_time_days]):
            failed.append(f"第{i}行：数值格式错误")
            continue

        # 根据日均销量和到货天数自动计算三个专业参数
        min_stock, rop, eoq = calc_stock_params(daily_sales, lead_time_days)

        # 按名称查找已有商品
        existing = db.query(Product).filter(
            Product.name == name, Product.deleted == False
        ).first()

        # SKU 唯一性检查（排除当前正在更新的商品）
        if sku:
            sku_exists = db.query(Product).filter(
                Product.sku == sku,
                Product.deleted == False,
                Product.id != (existing.id if existing else -1),
            ).first()
            if sku_exists:
                failed.append(f"第{i}行：SKU {sku} 已被其他商品使用")
                continue

        if existing:
            # 覆盖更新已有商品
            existing.sku = sku
            existing.unit = unit
            existing.current_stock = current_stock
            existing.daily_sales = daily_sales
            existing.lead_time_days = lead_time_days
            existing.min_stock = min_stock
            existing.rop = rop
            existing.eoq = eoq
        else:
            # 新增商品
            db.add(
                Product(
                    name=name,
                    sku=sku,
                    unit=unit,
                    current_stock=current_stock,
                    daily_sales=daily_sales,
                    lead_time_days=lead_time_days,
                    min_stock=min_stock,
                    rop=rop,
                    eoq=eoq,
                )
            )

        success += 1

    db.commit()

    return {
        "success": success,
        "failed_count": len(failed),
        "failed": failed,
    }


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    """商品详情"""
    product = db.query(Product).filter(
        Product.id == product_id, Product.deleted == False
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)):
    """编辑商品（安全库存/订货点/建议补货量由 AI 自动计算）"""
    product = db.query(Product).filter(
        Product.id == product_id, Product.deleted == False
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    update_data = data.model_dump(exclude_unset=True)

    if update_data.get("sku"):
        exists = db.query(Product).filter(
            Product.sku == update_data["sku"],
            Product.id != product_id,
            Product.deleted == False,
        ).first()
        if exists:
            raise HTTPException(status_code=400, detail="SKU 已存在")

    for key, value in update_data.items():
        setattr(product, key, value)

    # 根据日均销量和到货天数重新计算库存参数（日均销量为 0 时三个参数都归 0）
    product.min_stock, product.rop, product.eoq = calc_stock_params(
        product.daily_sales, product.lead_time_days
    )

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """删除商品（软删除）"""
    product = db.query(Product).filter(
        Product.id == product_id, Product.deleted == False
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")

    product.deleted = True
    # 释放 SKU，允许以后重建相同 SKU 的商品
    product.sku = None
    db.commit()
    return {"message": "删除成功"}
