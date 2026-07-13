from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from database import async_session
from models import Player, Organization, MapCell, City, Building

router = APIRouter()

class OrgCreateReq(BaseModel):
    vk_id: int
    name: str

class OrgDepositReq(BaseModel):
    vk_id: int
    resource: str
    amount: int

class BuyLandReq(BaseModel):
    vk_id: int
    cell_id: int

class BuildReq(BaseModel):
    vk_id: int
    cell_id: int
    building_type: str

@router.post("/api/org/create")
async def create_org(req: OrgCreateReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if player.organization_id:
            raise HTTPException(status_code=400, detail="Вы уже состоите в организации")
        if player.coins < 100:
            raise HTTPException(status_code=400, detail="Нужно 100 🪙")
            
        existing = (await session.execute(select(Organization).where(Organization.name == req.name))).scalars().first()
        if existing:
            raise HTTPException(status_code=400, detail="Название занято")
            
        city = (await session.execute(select(City).where(and_(City.q == player.q, City.r == player.r)))).scalars().first()
        city_id = city.id if city else None
        
        player.coins -= 100
        org = Organization(name=req.name, master_id=player.id, city_id=city_id)
        session.add(org)
        await session.flush()
        
        player.organization_id = org.id
        player.org_role = "master"
        await session.commit()
        return {"status": "ok"}

@router.post("/api/org/deposit")
async def org_deposit(req: OrgDepositReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if not player.organization_id:
            raise HTTPException(status_code=400, detail="Вы не в организации")
            
        org = (await session.execute(select(Organization).where(Organization.id == player.organization_id))).scalars().first()
        
        if req.resource == "coins":
            if player.coins < req.amount:
                raise HTTPException(status_code=400, detail="Недостаточно монет")
            player.coins -= req.amount
            org.coins += req.amount
        elif req.resource in ["wood", "stone", "iron", "fiber", "hide", "food"]:
            if getattr(player, req.resource) < req.amount:
                raise HTTPException(status_code=400, detail="Недостаточно ресурсов")
            setattr(player, req.resource, getattr(player, req.resource) - req.amount)
            setattr(org, req.resource, getattr(org, req.resource) + req.amount)
        else:
            raise HTTPException(status_code=400, detail="Неверный ресурс")
            
        await session.commit()
        return {"status": "ok"}

@router.post("/api/org/buy_land")
async def buy_land(req: BuyLandReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if player.org_role != "master":
            raise HTTPException(status_code=400, detail="Только Лидер организации может покупать землю")
            
        org = (await session.execute(select(Organization).where(Organization.id == player.organization_id))).scalars().first()
        cell = (await session.execute(select(MapCell).where(MapCell.id == req.cell_id))).scalars().first()
        
        if not cell or cell.controller_id is None or cell.owner_org_id is not None:
            raise HTTPException(status_code=400, detail="Ячейка не принадлежит городу или уже куплена")
            
        city = (await session.execute(select(City).where(City.id == cell.controller_id))).scalars().first()
        
        land_cost = 1000
        if org.coins < land_cost:
            raise HTTPException(status_code=400, detail=f"Нужно {land_cost} 🪙 в казне гильдии")
            
        org.coins -= land_cost
        city.coins += land_cost
        
        cell.owner_org_id = org.id
        cell.controller_id = None
        await session.commit()
        return {"status": "ok", "message": f"Земля успешно выкуплена у города {city.name}!"}

@router.post("/api/org/build")
async def build_on_land(req: BuildReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if player.org_role != "master":
            raise HTTPException(status_code=400, detail="Только Лидер может строить")
            
        org = (await session.execute(select(Organization).where(Organization.id == player.organization_id))).scalars().first()
        cell = (await session.execute(select(MapCell).where(MapCell.id == req.cell_id))).scalars().first()
        
        if not cell or cell.owner_org_id != org.id:
            raise HTTPException(status_code=400, detail="Эта земля не принадлежит вашей гильдии")
            
        existing_building = (await session.execute(select(Building).where(Building.cell_id == cell.id))).scalars().first()
        if existing_building:
            raise HTTPException(status_code=400, detail="На этой ячейке уже есть постройка")
            
        biome_reqs = {
            "sawmill": ["forest"],
            "mine": ["mountain", "highland"],
            "farm": ["steppe", "swamp"]
        }
        
        allowed_biomes = biome_reqs.get(req.building_type)
        if not allowed_biomes or cell.biome not in allowed_biomes:
            raise HTTPException(status_code=400, detail=f"Здание {req.building_type} нельзя построить в биоме {cell.biome}")
            
        build_wood = 500
        build_stone = 500
        if org.wood < build_wood or org.stone < build_stone:
            raise HTTPException(status_code=400, detail="Недостаточно стройматериалов (нужно 500 🪵 и 500 🪨 в банке гильдии)")
            
        org.wood -= build_wood
        org.stone -= build_stone
        
        building = Building(
            city_id=org.city_id,
            cell_id=cell.id,
            building_type=req.building_type,
            level=1,
            hp=100,
            max_hp=100
        )
        session.add(building)
        await session.commit()
        return {"status": "ok", "message": f"Постройка {req.building_type} успешно возведена!"}
