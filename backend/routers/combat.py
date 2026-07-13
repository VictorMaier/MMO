from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from database import async_session
from models import Player, Combat, City
from game.combat_engine import CombatEngine
from routers.player_api import get_player_stats, add_skill_xp

router = APIRouter()

class CombatActionReq(BaseModel):
    vk_id: int
    action: str
    target_key: str = ""

@router.get("/api/combat/state")
async def get_combat_state(vk_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Player)
            .options(selectinload(Player.combat), selectinload(Player.equipment))
            .where(Player.vk_id == vk_id)
        )
        player = result.scalars().first()
        if not player:
            raise HTTPException(status_code=404, detail="Игрок не найден")
            
        if not player.combat:
            return {"in_combat": False}
            
        return {"in_combat": True, "state": player.combat.combat_state}

@router.post("/api/combat/action")
async def combat_action(req: CombatActionReq):
    async with async_session() as session:
        result = await session.execute(
            select(Player)
            .options(selectinload(Player.combat), selectinload(Player.equipment))
            .where(Player.vk_id == req.vk_id)
        )
        player = result.scalars().first()
        if not player or not player.combat:
            raise HTTPException(status_code=400, detail="Вы не в бою")
            
        db_combat = player.combat
        state = dict(db_combat.combat_state)
        player_stats = get_player_stats(player)
        
        active_key = state["turn_order"][state["current_turn_index"]]
        active_unit = CombatEngine.find_unit(state, active_key)
        
        if active_unit and active_unit.get("id") == player.id and active_unit["hp"] > 0:
            target_key = req.target_key
            if not target_key and state["enemies"]:
                living_enemies = [e for e in state["enemies"] if e["hp"] > 0]
                if living_enemies:
                    target_key = living_enemies[0]["key"]
                    
            success = CombatEngine.execute_action(state, req.action, target_key)
            if not success and req.action != "skip":
                raise HTTPException(status_code=400, detail="Неверное действие или недостаточно AP")
                
            if req.action == "skip":
                active_unit["ap"] = 0
                
            if active_unit["ap"] <= 0:
                CombatEngine.next_turn(state)
                
        CombatEngine.process_ai_turns(state, player.id)
        
        player_alive = any(a["hp"] > 0 for a in state["allies"])
        enemies_alive = any(e["hp"] > 0 for e in state["enemies"])
        
        if not enemies_alive:
            player.current_hp = next((a["hp"] for a in state["allies"] if a["id"] == player.id), player_stats["max_hp"])
            xp_msg = add_skill_xp(player, "one_handed", 20)
            player.essence += 20
            state["action_log"].append(f"Победа! Получено: Эссенция 🔮 x20. {xp_msg}")
            await session.delete(db_combat)
            await session.commit()
            return {"status": "won", "log": state["action_log"]}
            
        if not player_alive:
            player.current_hp = player_stats["max_hp"]
            city = (await session.execute(select(City))).scalars().first()
            if city:
                player.q = city.q
                player.r = city.r
            state["action_log"].append("Вы погибли! Возрождение в городе...")
            await session.delete(db_combat)
            await session.commit()
            return {"status": "dead", "log": state["action_log"]}
            
        db_combat.combat_state = state
        ally_state = next((a for a in state["allies"] if a["id"] == player.id), None)
        if ally_state:
            player.current_hp = ally_state["hp"]
            player.energy = ally_state["energy"]
        
        await session.commit()
        return {"status": "continue", "log": state["action_log"]}
