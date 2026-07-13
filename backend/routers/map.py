import random
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from database import async_session
from models import Player, MapCell, City, Equipment, Combat
from game.map_utils import hex_distance, is_zone_more_dangerous
from game.combat_engine import CombatEngine
from routers.player_api import get_player_stats

router = APIRouter()

ENERGY_COSTS = {"city": 1, "forest": 2, "highland": 2, "mountain": 3, "steppe": 2, "swamp": 3}

class MoveRequest(BaseModel):
    vk_id: int
    target_q: int
    target_r: int
    force: bool = False

class ExploreReq(BaseModel):
    vk_id: int

@router.get("/api/map")
async def fetch_map(vk_id: int = 1):
    async with async_session() as session:
        result = await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == vk_id)
        )
        player = result.scalars().first()
        
        if not player:
            cities = await session.execute(select(City))
            city_list = cities.scalars().all()
            start_city = random.choice(city_list) if city_list else None
            q, r = (start_city.q, start_city.r) if start_city else (0, 0)
            c_id = start_city.id if start_city else None
            player = Player(
                vk_id=vk_id, q=q, r=r, citizenship_city_id=c_id, 
                citizenship_status="citizen", disabled_warnings=[]
            )
            session.add(player)
            await session.flush()
            tools = ["t1_axe", "t1_pickaxe", "t1_hammer", "t1_sickle", "t1_knife"]
            for t in tools:
                session.add(Equipment(player_id=player.id, item_id=t))
            await session.commit()

        view_distance = 6
        cells_query = await session.execute(
            select(MapCell).where(and_(
                MapCell.q >= player.q - view_distance, MapCell.q <= player.q + view_distance,
                MapCell.r >= player.r - view_distance, MapCell.r <= player.r + view_distance
            ))
        )
        
        valid_cells = []
        for c in cells_query.scalars().all():
            if hex_distance(c.q, c.r, player.q, player.r) <= view_distance:
                valid_cells.append({
                    "id": c.id, "q": c.q, "r": c.r, "biome": c.biome, 
                    "has_road": c.has_road, "risk_zone": c.risk_zone
                })

        cities_query = await session.execute(select(City))
        cities = [{"id": c.id, "name": c.name, "q": c.q, "r": c.r} for c in cities_query.scalars().all()]

        other_players_query = await session.execute(
            select(Player).where(and_(
                Player.vk_id != vk_id,
                Player.q >= player.q - view_distance, Player.q <= player.q + view_distance,
                Player.r >= player.r - view_distance, Player.r <= player.r + view_distance
            ))
        )
        other_players = []
        for p in other_players_query.scalars().all():
            if hex_distance(p.q, p.r, player.q, player.r) <= view_distance:
                other_players.append({"q": p.q, "r": p.r, "vk_id": p.vk_id})

    return {
        "cells": valid_cells, "cities": cities, "other_players": other_players,
        "player": {
            "q": player.q, "r": player.r, "energy": player.energy, "hp": player.current_hp,
            "inventory": {
                "wood": player.wood, "stone": player.stone, "iron": player.iron, 
                "fiber": player.fiber, "hide": player.hide, "food": player.food, 
                "coins": player.coins, "essence": player.essence
            }
        }
    }

@router.post("/api/move")
async def move_player(req: MoveRequest):
    async with async_session() as session:
        result = await session.execute(select(Player).options(selectinload(Player.combat)).where(Player.vk_id == req.vk_id))
        player = result.scalars().first()
        if player.combat:
            raise HTTPException(status_code=400, detail="Вы в бою!")
            
        current_cell = (await session.execute(select(MapCell).where(and_(MapCell.q == player.q, MapCell.r == player.r)))).scalars().first()
        target_cell = (await session.execute(select(MapCell).where(and_(MapCell.q == req.target_q, MapCell.r == req.target_r)))).scalars().first()
        
        if not target_cell: raise HTTPException(status_code=400, detail="Край мира!")
        dist = hex_distance(player.q, player.r, req.target_q, req.target_r)
        if dist > 1: raise HTTPException(status_code=400, detail="Слишком далеко!")
            
        if is_zone_more_dangerous(current_cell.risk_zone, target_cell.risk_zone) and not req.force:
            if target_cell.risk_zone not in (player.disabled_warnings or []):
                return {
                    "status": "warning_trigger",
                    "risk_zone": target_cell.risk_zone,
                    "message": f"Вы переходите в более опасную зону: {target_cell.risk_zone.upper()}!"
                }
                
        cost = 1 if target_cell.has_road else ENERGY_COSTS.get(target_cell.biome, 2)
        if player.energy < cost: raise HTTPException(status_code=400, detail=f"Нужно {cost} ⚡ энергии!")
            
        player.q = req.target_q
        player.r = req.target_r
        player.energy -= cost
        await session.commit()
        return {"status": "ok"}

@router.post("/api/explore")
async def explore_cell(req: ExploreReq):
    async with async_session() as session:
        player = (await session.execute(
            select(Player).options(selectinload(Player.combat), selectinload(Player.equipment)).where(Player.vk_id == req.vk_id)
        )).scalars().first()

        if player.combat:
            raise HTTPException(status_code=400, detail="Вы в бою!")
        if player.energy < 5:
            raise HTTPException(status_code=400, detail="Недостаточно энергии (нужно 5 ⚡)")

        cell = (await session.execute(select(MapCell).where(and_(MapCell.q == player.q, MapCell.r == player.r)))).scalars().first()
        if cell.is_city:
            raise HTTPException(status_code=400, detail="В городе нельзя исследовать. Идите в дикие земли.")

        player.energy -= 5

        if random.random() < 0.3:
            player_stats = get_player_stats(player)
            monster_template = {
                "name": "Дикий Волк 🐺" if cell.biome in ["forest", "field", "swamp"] else "Горный Гоблин 👺",
                "hp": 50, "damage": 12, "defense": 5, "speed": 6.0
            }
            combat_state = CombatEngine.initialize_battle(player, player_stats, monster_template)
            
            CombatEngine.process_ai_turns(combat_state, player.id)
            
            player_alive = any(a["hp"] > 0 for a in combat_state["allies"])
            if not player_alive:
                player.current_hp = combat_state["allies"][0]["max_hp"]
                city = (await session.execute(select(City))).scalars().first()
                if city:
                    player.q = city.q
                    player.r = city.r
                await session.commit()
                return {"status": "combat", "message": f"Вы встретили врага: {monster_template['name']}... и он убил вас первым же ударом!"}

            new_combat = Combat(player_id=player.id, combat_state=combat_state)
            session.add(new_combat)
            await session.commit()
            return {"status": "combat", "message": f"Вы встретили врага: {monster_template['name']}!"}

        resources_map = {
            "forest": ["wood", "hide", "stone"],
            "highland": ["stone", "iron", "wood"],
            "mountain": ["iron", "stone", "fiber"],
            "steppe": ["hide", "fiber", "iron"],
            "swamp": ["fiber", "wood", "hide"]
        }
        res_list = resources_map.get(cell.biome, ["food"])
        found_res = random.choice(res_list)
        amount = random.randint(2, 5)

        setattr(player, found_res, getattr(player, found_res) + amount)
        
        essence_msg = ""
        if random.random() < 0.15:
            ess = random.randint(5, 10)
            player.essence += ess
            essence_msg = f" и {ess} 🔮 Эссенции"

        await session.commit()
        res_names = {"wood": "🪵 Дерево", "stone": "🪨 Камень", "iron": "⚙️ Железо", "fiber": "🌿 Волокно", "hide": "🦇 Шкуры", "food": "🍖 Еда"}
        return {"status": "ok", "message": f"Вы нашли {amount} {res_names.get(found_res, found_res)}{essence_msg}."}
