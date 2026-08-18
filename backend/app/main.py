"""FastAPI 入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base
from . import models  # 确保模型被注册
from .routers import auth, products, stock, ai, dashboard, stats

# 创建所有表（骨架阶段直接建表，后续可改为 Alembic 迁移）
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI智能库存助手", version="0.1.0")

# 允许跨域（前端开发时端口不同）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(stock.router)
app.include_router(ai.router)
app.include_router(dashboard.router)
app.include_router(stats.router)


@app.get("/api/health")
def health():
    """健康检查接口"""
    return {"status": "ok"}
