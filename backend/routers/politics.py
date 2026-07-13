from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from database import async_session
from models import Player, City, CityCandidate, CityVote, Law, LawVote, CityContract, MapCell, ExpansionContract, Organization
import datetime

router = APIRouter()

class IdReq(BaseModel):
    vk_id: int
    obj_id: int

class ProposalReq(BaseModel):
    vk_id: int
    tax_rate: int

class ExpansionReq(BaseModel):
    vk_id: int
    target_q: int
    target_r: int
    reward_coins: int

@router.get("/api/city/townhall")
async def get_townhall(vk_id: int):
    async with async_session() as session:
        player = (await session.execute(
            select(Player).options(selectinload(Player.organization)).where(Player.vk_id == vk_id)
        )).scalars().first()
        
        city = (await session.execute(
            select(City).options(selectinload(City.mayor)).where(and_(City.q == player.q, City.r == player.r))
        )).scalars().first()
        
        if not city:
            raise HTTPException(status_code=400, detail="Вы не в городе")
            
        cit_status = "Вы не гражданин"
        if player.citizenship_city_id == city.id:
            if player.citizenship_status == "citizen":
                cit_status = "Гражданин"
            else:
                rem = int((player.citizenship_timer - datetime.datetime.utcnow()).total_seconds() / 60)
                cit_status = f"Карантин (осталось {max(0, rem)} мин)"
                
        cands = (await session.execute(
            select(CityCandidate).where(CityCandidate.city_id == city.id).order_by(CityCandidate.votes.desc())
        )).scalars().all()
        
        has_voted = (await session.execute(
            select(CityVote).where(and_(CityVote.city_id == city.id, CityVote.player_id == player.id))
        )).scalars().first() is not None
        
        is_cand = any(c.player_id == player.id for c in cands)
        laws = (await session.execute(
            select(Law).where(and_(Law.city_id == city.id, Law.status == "voting"))
        )).scalars().all()
        
        contracts = (await session.execute(
            select(CityContract).where(CityContract.city_id == city.id)
        )).scalars().all()
        
        is_mayor = city.mayor_id == player.id
        is_council = player.id in (city.council_ids or [])
        
        return {
            "city_name": city.name,
            "tax_rate": float(city.tax_rate),
            "treasury": city.coins,
            "mayor_name": f"Игрок {city.mayor.vk_id}" if city.mayor else "Нет",
            "citizenship": cit_status,
            "elections": {
                "ends_in": max(0, int((city.election_ends_at - datetime.datetime.utcnow()).total_seconds() / 60)) if city.election_ends_at else 0,
                "can_vote": not has_voted and player.citizenship_status == "citizen",
                "can_nominate": not is_cand and player.citizenship_status == "citizen",
                "candidates": [{"id": c.player_id, "votes": c.votes} for c in cands]
            },
            "laws": [{"id": l.id, "new_tax": l.new_tax, "for": l.votes_for, "against": l.votes_against} for l in laws],
            "contracts": [{"id": c.id, "res": c.resource_type, "req": c.req_amount, "cur": c.cur_amount, "reward": c.reward_coins, "status": c.status} for c in contracts],
            "perms": {"is_mayor": is_mayor, "is_council": is_council, "is_master": player.org_role == "master"}
        }

@router.post("/api/city/election/nominate")
async def election_nominate(req: IdReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if player.citizenship_status != "citizen":
            raise HTTPException(status_code=400, detail="Только граждане могут избираться")
        if player.coins < 100:
            raise HTTPException(status_code=400, detail="Нужно 100 🪙 для взноса")
            
        city = (await session.execute(
            select(City).where(and_(City.q == player.q, City.r == player.r))
        )).scalars().first()
        
        player.coins -= 100
        session.add(CityCandidate(city_id=city.id, player_id=player.id))
        await session.commit()
        return {"status": "ok"}

@router.post("/api/city/election/vote")
async def election_vote(req: IdReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        city = (await session.execute(
            select(City).where(and_(City.q == player.q, City.r == player.r))
        )).scalars().first()
        
        has_voted = (await session.execute(
            select(CityVote).where(and_(CityVote.city_id == city.id, CityVote.player_id == player.id))
        )).scalars().first() is not None
        if has_voted:
            raise HTTPException(status_code=400, detail="Вы уже проголосовали!")
            
        cand = (await session.execute(
            select(CityCandidate).where(and_(CityCandidate.city_id == city.id, CityCandidate.player_id == req.obj_id))
        )).scalars().first()
        if not cand:
            raise HTTPException(status_code=400, detail="Кандидат не найден")
            
        cand.votes += 1
        session.add(CityVote(city_id=city.id, player_id=player.id))
        await session.commit()
        return {"status": "ok"}

@router.post("/api/city/law/propose")
async def propose_law(req: ProposalReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        city = (await session.execute(
            select(City).where(and_(City.q == player.q, City.r == player.r))
        )).scalars().first()
        
        if city.mayor_id != player.id:
            raise HTTPException(status_code=400, detail="Только Мэр может предлагать законы")
        if req.tax_rate < 0 or req.tax_rate > 50:
            raise HTTPException(status_code=400, detail="Налог должен быть от 0 до 50%")
            
        session.add(Law(city_id=city.id, new_tax=req.tax_rate, ends_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10)))
        await session.commit()
        return {"status": "ok"}

@router.post("/api/city/expansion/propose")
async def propose_expansion(req: ExpansionReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        city = (await session.execute(select(City).where(City.mayor_id == player.id))).scalars().first()
        if not city:
            raise HTTPException(status_code=400, detail="Вы не Мэр!")
            
        target_cell = (await session.execute(
            select(MapCell).where(and_(MapCell.q == req.target_q, MapCell.r == req.target_r))
        )).scalars().first()
        if not target_cell:
            raise HTTPException(status_code=400, detail="Ячейка не найдена!")
            
        if target_cell.controller_id is not None:
            raise HTTPException(status_code=400, detail="Клетка уже захвачена!")
            
        if city.coins < req.reward_coins:
            raise HTTPException(status_code=400, detail="Недостаточно монет в городской казне!")
            
        city.coins -= req.reward_coins
        contract = ExpansionContract(
            city_id=city.id,
            target_cell_id=target_cell.id,
            organization_id=None,
            status="pending",
            reward_coins=req.reward_coins
        )
        session.add(contract)
        await session.commit()
        return {"status": "ok"}

@router.post("/api/city/expansion/accept")
async def accept_expansion(req: IdReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if player.org_role != "master":
            raise HTTPException(status_code=400, detail="Только лидер организации может принять контракт!")
            
        contract = (await session.execute(
            select(ExpansionContract).where(and_(ExpansionContract.id == req.obj_id, ExpansionContract.status == "pending"))
        )).scalars().first()
        if not contract:
            raise HTTPException(status_code=400, detail="Контракт недоступен")
            
        contract.organization_id = player.organization_id
        contract.status = "active"
        contract.flag_placed_at = datetime.datetime.utcnow()
        await session.commit()
        return {"status": "ok"}
