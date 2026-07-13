import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
from sqlalchemy import select, and_

from database import engine, Base, async_session
from models.map import ExpansionContract, MapCell
from models.organization import Organization
from models.player import Player
from routers import map, combat, craft, market, politics, gacha, organization, player_api
from bot import run_vk_bot, send_bot_notification

async def flag_capture_ticker():
    while True:
        await asyncio.sleep(3600)
        async with async_session() as session:
            contracts = (await session.execute(
                select(ExpansionContract).where(ExpansionContract.status == "active")
            )).scalars().all()
            
            for c in contracts:
                cell = (await session.execute(select(MapCell).where(MapCell.id == c.target_cell_id))).scalars().first()
                org = (await session.execute(select(Organization).where(Organization.id == c.organization_id))).scalars().first()
                
                if not cell or not org:
                    continue

                defenders = (await session.execute(
                    select(Player).where(and_(Player.organization_id == org.id, Player.q == cell.q, Player.r == cell.r))
                )).scalars().all()
                
                if len(defenders) >= 1:
                    c.capture_progress += 1
                    await send_bot_notification(org.master_id, f"Проверка флага на клетке ({cell.q}, {cell.r}) пройдена! Прогресс: {c.capture_progress}/3.")
                else:
                    c.capture_progress -= 1
                    await send_bot_notification(org.master_id, f"Внимание! На клетке флага ({cell.q}, {cell.r}) нет защитников. Прогресс падает до {c.capture_progress}/3.")
                    
                if c.capture_progress >= 3:
                    c.status = "completed"
                    cell.controller_id = c.city_id
                    org.coins += c.reward_coins
                    
                    members = (await session.execute(select(Player).where(Player.organization_id == org.id))).scalars().all()
                    for m in members:
                        await send_bot_notification(m.vk_id, f"Земля ({cell.q}, {cell.r}) захвачена вашей гильдией! В банк зачислено {c.reward_coins} монет.")
                elif c.capture_progress < 0:
                    c.status = "failed"
                    await send_bot_notification(org.master_id, f"Контракт провален! Флаг на клетке ({cell.q}, {cell.r}) исчез.")
                    
            await session.commit()

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    ticker_task = asyncio.create_task(flag_capture_ticker())
    bot_task = asyncio.create_task(run_vk_bot())
    yield
    ticker_task.cancel()
    bot_task.cancel()

app = FastAPI(title="MMO WebApp API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(map.router)
app.include_router(player_api.router)
app.include_router(combat.router)
app.include_router(craft.router)
app.include_router(market.router)
app.include_router(politics.router)
app.include_router(gacha.router)
app.include_router(organization.router)

frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def read_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))
