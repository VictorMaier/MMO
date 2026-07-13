import math
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified
from database import async_session
from models import Player, Equipment, City

router = APIRouter()

class EquipRequest(BaseModel):
    vk_id: int
    equip_id: int

class PersonaRequest(BaseModel):
    vk_id: int
    persona_id: str

class PlayerRequest(BaseModel):
    vk_id: int

RECIPES = {
    "forge": {
        "t1_sword": {"name": "Железный меч 🗡️", "cost": {"iron": 15, "wood": 5}},
        "t2_sword": {"name": "Стальной меч 🗡️", "cost": {"iron": 50, "wood": 10}}
    },
    "tannery": {
        "t1_armor": {"name": "Кожаная куртка 🧥", "cost": {"hide": 20, "fiber": 10}}
    },
    "toolmaker": {
        "t1_axe": {"name": "Топор новичка 🪓", "cost": {"wood": 5, "stone": 3}},
        "t1_pickaxe": {"name": "Кирка новичка ⛏️", "cost": {"wood": 5, "stone": 5}},
        "t1_hammer": {"name": "Молот новичка 🔨", "cost": {"wood": 5, "stone": 5}},
        "t1_sickle": {"name": "Серп новичка 🌿", "cost": {"wood": 5, "stone": 2}},
        "t1_knife": {"name": "Нож свежевателя 🔪", "cost": {"wood": 5, "stone": 2}}
    }
}

ITEMS_DB = {
    "t1_sword": {"name": "Железный меч 🗡️", "type": "weapon", "damage": 20, "req_skill": "one_handed", "req_lvl": 1},
    "t2_sword": {"name": "Стальной меч 🗡️", "type": "weapon", "damage": 35, "req_skill": "one_handed", "req_lvl": 10},
    "t1_armor": {"name": "Кожаная куртка 🧥", "type": "armor", "hp_bonus": 10, "defense": 10, "req_skill": "one_handed", "req_lvl": 1},
    "t1_axe": {"name": "Топор новичка 🪓", "type": "tool", "tool_type": "woodcutting", "req_skill": "woodcutting", "req_lvl": 1},
    "t1_pickaxe": {"name": "Кирка новичка ⛏️", "type": "tool", "tool_type": "mining_ore", "req_skill": "mining_ore", "req_lvl": 1},
    "t1_hammer": {"name": "Молот новичка 🔨", "type": "tool", "tool_type": "mining_stone", "req_skill": "mining_stone", "req_lvl": 1},
    "t1_sickle": {"name": "Серп новичка 🌿", "type": "tool", "tool_type": "harvesting", "req_skill": "harvesting", "req_lvl": 1},
    "t1_knife": {"name": "Нож свежевателя 🔪", "type": "tool", "tool_type": "skinning", "req_skill": "skinning", "req_lvl": 1},
    "gacha_luck_ring": {"name": "Кольцо Удачи 💍", "type": "accessory", "crit_chance": 5},
    "gacha_vamp_ring": {"name": "Кольцо Вампира 🩸", "type": "accessory", "crit_chance": 8},
    "gacha_time_ring": {"name": "Кольцо Времени ⏳", "type": "accessory", "speed_bonus": 1},
    "gacha_archmage_amulet": {"name": "Амулет Архимага 🧙", "type": "accessory", "energy_bonus": 30},
    "gacha_infinity_cloak": {"name": "Плащ Бесконечности 🌌", "type": "accessory", "hp_bonus": 30}
}

SKILL_NAMES = {
    "woodcutting": "Лесозаготовка 🪓", "mining_stone": "Добыча камня 🪨", "mining_ore": "Горное дело ⛏️",
    "harvesting": "Сбор волокна 🌿", "skinning": "Свежевание 🔪", "blacksmithing": "Кузнечное дело ⚒️",
    "leatherworking": "Кожевничество 🧵", "one_handed": "Владение мечом 🗡️"
}

PERSONAS_DB = {
    "p_healer": {"name": "Кровавый Целитель", "rarity": "Rare", "desc": "40% нанесенного урона лечит вас."},
    "p_golem": {"name": "Голем", "rarity": "Rare", "desc": "+40% к Макс. HP. У вас -1 ОД в бою."},
    "p_duelist": {"name": "Безрассудный Дуэлянт", "rarity": "Rare", "desc": "+50% к урону, но защита снижена вдвое."},
    "p_sturdy": {"name": "Крепкий Телом", "rarity": "Common", "desc": "+10% к Макс. HP."}
}

def get_exp_required(level):
    if level >= 100:
        return 999999999
    return int((100 * level) + ((level ** 2.2) * 2) + (math.log(level + 1) * 50))

def add_skill_xp(player, skill_id, amount):
    if player.skills is None:
        player.skills = {}
    skills = dict(player.skills)
    if skill_id not in skills:
        skills[skill_id] = {"level": 1, "xp": 0}
    skills[skill_id]["xp"] += amount
    msg = ""
    while True:
        lvl = skills[skill_id]["level"]
        if lvl >= 100:
            skills[skill_id]["xp"] = 0
            break
        req = get_exp_required(lvl)
        if skills[skill_id]["xp"] >= req:
            skills[skill_id]["xp"] -= req
            skills[skill_id]["level"] += 1
            msg += f"\n🆙 {SKILL_NAMES[skill_id]} повышен до {lvl+1} ур!"
        else:
            break
    player.skills = skills
    flag_modified(player, "skills")
    return msg

def get_player_stats(player):
    stats = {"max_hp": 100, "damage": 5, "defense": 0, "ap_mod": 0, "speed": 5.0, "crit_chance": 5, "crit_damage": 150}
    for eq in player.equipment:
        if eq.is_equipped:
            item = ITEMS_DB.get(eq.item_id, {})
            stats["max_hp"] += item.get("hp_bonus", 0)
            stats["damage"] += item.get("damage", 0)
            stats["defense"] += item.get("defense", 0)
            stats["speed"] += item.get("speed_bonus", 0)
            stats["crit_chance"] += item.get("crit_chance", 0)
            stats["crit_damage"] += item.get("crit_damage_bonus", 0)
            
    lvl = player.skills.get("one_handed", {}).get("level", 1) if player.skills else 1
    stats["damage"] = int(stats["damage"] * (1.0 + (lvl - 1) * 0.005))
    hp_mult, dmg_mult, def_mult = 1.0, 1.0, 1.0
    active_p = player.active_personas if player.active_personas else []
    if "p_golem" in active_p:
        hp_mult += 0.4
        stats["ap_mod"] -= 1
    if "p_sturdy" in active_p:
        hp_mult += 0.1
    if "p_duelist" in active_p:
        dmg_mult += 0.5
        def_mult *= 0.5
    stats["max_hp"] = int(stats["max_hp"] * hp_mult)
    stats["damage"] = int(stats["damage"] * dmg_mult)
    stats["defense"] = int(stats["defense"] * def_mult)
    return stats

@router.get("/api/profile")
async def get_profile(vk_id: int):
    async with async_session() as session:
        result = await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == vk_id)
        )
        player = result.scalars().first()
        stats = get_player_stats(player)
        if player.current_hp > stats["max_hp"]:
            player.current_hp = stats["max_hp"]
        eq_list = []
        for eq in player.equipment:
            item_data = ITEMS_DB.get(eq.item_id, {})
            req_s = item_data.get("req_skill")
            req_l = item_data.get("req_lvl", 1)
            req_str = f" [Треб: {SKILL_NAMES.get(req_s, '')} {req_l} ур.]" if req_s else ""
            if item_data.get("type") == "weapon":
                stats_str = f"Урон: {item_data.get('damage',0)}{req_str}"
            elif item_data.get("type") == "armor":
                stats_str = f"HP: +{item_data.get('hp_bonus',0)}, Защ: {item_data.get('defense',0)}{req_str}"
            elif item_data.get("type") == "accessory":
                stats_str = f"Аксессуар"
            else:
                stats_str = f"Инструмент{req_str}"
            eq_list.append({
                "id": eq.id, "item_id": eq.item_id, "name": item_data.get("name", "Неизвестно"),
                "type": item_data.get("type", "unknown"), "is_equipped": eq.is_equipped, "stats_str": stats_str
            })
        skills_data = {}
        if player.skills:
            for k, v in player.skills.items():
                skills_data[k] = {"level": v["level"], "xp": v["xp"], "req": get_exp_required(v["level"])}
        return {
            "stats": stats, "current_hp": player.current_hp, "equipment": eq_list,
            "unlocked_personas": player.unlocked_personas if player.unlocked_personas else [],
            "active_personas": player.active_personas if player.active_personas else [],
            "personas_db": PERSONAS_DB, "skills": skills_data, "skill_names": SKILL_NAMES,
            "coins": player.coins, "destiny_shards": player.destiny_shards
        }

@router.post("/api/equip")
async def equip_item(req: EquipRequest):
    async with async_session() as session:
        result = await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == req.vk_id)
        )
        player = result.scalars().first()
        target_eq = next((eq for eq in player.equipment if eq.id == req.equip_id), None)
        target_item_data = ITEMS_DB.get(target_eq.item_id, {})
        target_type = target_item_data.get("type")
        if target_type == "tool":
            raise HTTPException(status_code=400, detail="Инструменты работают из инвентаря.")
        req_skill = target_item_data.get("req_skill")
        req_lvl = target_item_data.get("req_lvl", 1)
        if req_skill:
            p_lvl = player.skills.get(req_skill, {}).get("level", 1) if player.skills else 1
            if p_lvl < req_lvl:
                raise HTTPException(status_code=400, detail=f"Требуется: {SKILL_NAMES.get(req_skill)} {req_lvl} ур.")
        if target_eq.is_equipped:
            target_eq.is_equipped = False
        else:
            for eq in player.equipment:
                if eq.is_equipped and ITEMS_DB.get(eq.item_id, {}).get("type") == target_type:
                    eq.is_equipped = False
            target_eq.is_equipped = True
        stats = get_player_stats(player)
        if player.current_hp > stats["max_hp"]:
            player.current_hp = stats["max_hp"]
        await session.commit()
        return {"status": "ok"}

@router.post("/api/persona/toggle")
async def toggle_persona(req: PersonaRequest):
    async with async_session() as session:
        result = await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == req.vk_id)
        )
        player = result.scalars().first()
        active = list(player.active_personas) if player.active_personas else []
        if req.persona_id in active:
            active.remove(req.persona_id)
        else:
            if len(active) >= 3:
                raise HTTPException(status_code=400, detail="Максимум 3 активных личности!")
            active.append(req.persona_id)
        player.active_personas = active
        stats = get_player_stats(player)
        if player.current_hp > stats["max_hp"]:
            player.current_hp = stats["max_hp"]
        await session.commit()
        return {"status": "ok"}

@router.post("/api/rest")
async def rest_player(req: PlayerRequest):
    async with async_session() as session:
        result = await session.execute(
            select(Player).options(selectinload(Player.equipment)).where(Player.vk_id == req.vk_id)
        )
        player = result.scalars().first()
        player.energy = 100
        player.current_hp = get_player_stats(player)["max_hp"]
        player.iron += 500
        player.wood += 500
        player.hide += 500
        player.fiber += 500
        player.stone += 500
        player.essence += 1600
        player.coins += 10000
        await session.commit()
        return {"status": "ok", "message": "Энергия и ресурсы получены!"}

@router.get("/api/recipes")
async def get_recipes():
    return RECIPES
