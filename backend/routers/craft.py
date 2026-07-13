import random
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from database import async_session
from models import Player, Equipment, City
from routers.player_api import add_skill_xp, RECIPES, ITEMS_DB

router = APIRouter()

class CraftReq(BaseModel):
    vk_id: int
    item_id: str

class RepairReq(BaseModel):
    vk_id: int
    equip_id: int

@router.post("/api/craft")
async def craft_item(req: CraftReq):
    async with async_session() as session:
        player = (await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == req.vk_id)
        )).scalars().first()
        
        city = (await session.execute(select(City).where(and_(City.q == player.q, City.r == player.r)))).scalars().first()
        if not city:
            raise HTTPException(status_code=400, detail="Крафт у мастеров доступен только в городе")
            
        recipe = None
        for cat in RECIPES.values():
            if req.item_id in cat:
                recipe = cat[req.item_id]
                break
        if not recipe:
            raise HTTPException(status_code=400, detail="Рецепт не найден")
            
        for res, amt in recipe["cost"].items():
            if getattr(player, res) < amt:
                raise HTTPException(status_code=400, detail=f"Недостаточно {res}")
                
        base_fee = 50
        city_tax = int(base_fee * (float(city.craft_tax) / 100.0))
        total_fee = base_fee + city_tax
        
        if player.coins < total_fee:
            raise HTTPException(status_code=400, detail=f"Нужно {total_fee} 🪙 для оплаты работы")
            
        for res, amt in recipe["cost"].items():
            setattr(player, res, getattr(player, res) - amt)
            
        player.coins -= total_fee
        city.coins += city_tax
        
        for eq in player.equipment:
            if eq.is_equipped:
                eq.durability = max(0, eq.durability - 1)
                
        session.add(Equipment(player_id=player.id, item_id=req.item_id, durability=100, max_durability=100))
        
        item_type = ITEMS_DB.get(req.item_id, {}).get("type")
        skill_id = "blacksmithing" if item_type in ["weapon", "tool"] else "leatherworking"
        xp_msg = add_skill_xp(player, skill_id, 20)
        
        await session.commit()
        return {"status": "ok", "message": f"Скрафчено: {recipe['name']}! Налог {city_tax} 🪙 ушел городу.{xp_msg}"}

@router.post("/api/repair")
async def repair_item(req: RepairReq):
    async with async_session() as session:
        player = (await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == req.vk_id)
        )).scalars().first()
        
        city = (await session.execute(select(City).where(and_(City.q == player.q, City.r == player.r)))).scalars().first()
        if not city:
            raise HTTPException(status_code=400, detail="Ремонт доступен только у кузнецов в городе")
            
        eq = next((e for e in player.equipment if e.id == req.equip_id), None)
        if not eq:
            raise HTTPException(status_code=404, detail="Предмет не найден")
            
        if eq.durability >= eq.max_durability:
            raise HTTPException(status_code=400, detail="Предмет полностью цел")
            
        item_data = ITEMS_DB.get(eq.item_id, {})
        tier_mod = item_data.get("req_lvl", 1) * 2
        repair_cost = int((eq.max_durability - eq.durability) * tier_mod)
        
        if player.coins < repair_cost:
            raise HTTPException(status_code=400, detail=f"Нужно {repair_cost} 🪙")
            
        player.coins -= repair_cost
        eq.durability = eq.max_durability
        await session.commit()
        return {"status": "ok", "message": f"Предмет {item_data.get('name')} отремонтирован за {repair_cost} 🪙"}
