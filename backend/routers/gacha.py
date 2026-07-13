import random
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from database import async_session
from models import Player, Equipment
from routers.player_api import PERSONAS_DB

router = APIRouter()

GACHA_ITEMS = {
    "uncommon": ["gacha_luck_ring", "catalyst_uncommon"],
    "rare": ["gacha_vamp_ring", "catalyst_rare"],
    "epic": ["gacha_time_ring", "gacha_archmage_amulet", "catalyst_epic"],
    "legendary": ["gacha_infinity_cloak", "catalyst_legendary"]
}

class RollReq(BaseModel):
    vk_id: int
    rolls_count: int

def determine_roll_rarity(player):
    player.gacha_pity_10 += 1
    player.gacha_pity_90 += 1
    
    if player.gacha_pity_90 >= 90:
        player.gacha_pity_90 = 0
        player.gacha_pity_10 = 0
        return "legendary"
        
    if player.gacha_pity_10 >= 10:
        player.gacha_pity_10 = 0
        rand = random.random()
        if rand < 0.05:
            player.gacha_pity_90 = 0
            return "legendary"
        elif rand < 0.25:
            return "epic"
        else:
            return "rare"
            
    rand = random.random()
    if rand < 0.01:
        player.gacha_pity_90 = 0
        player.gacha_pity_10 = 0
        return "legendary"
    elif rand < 0.05:
        player.gacha_pity_10 = 0
        return "epic"
    elif rand < 0.15:
        player.gacha_pity_10 = 0
        return "rare"
    elif rand < 0.30:
        return "uncommon"
    else:
        return "common"

def get_personality_of_rarity(rarity):
    match_keys = [k for k, v in PERSONAS_DB.items() if v.get("rarity", "Common").lower() == rarity]
    if match_keys:
        return random.choice(match_keys)
    return random.choice(list(PERSONAS_DB.keys()))

@router.post("/api/gacha/roll")
async def roll_gacha(req: RollReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        if not player:
            raise HTTPException(status_code=404)
            
        if req.rolls_count not in [1, 10]:
            raise HTTPException(status_code=400, detail="Допустимо только 1 или 10 роллов")
            
        cost = 160 if req.rolls_count == 1 else 1440
        if player.essence < cost:
            raise HTTPException(status_code=400, detail=f"Недостаточно эссенций (нужно {cost} 🔮)")
            
        player.essence -= cost
        results = []
        
        for _ in range(req.rolls_count):
            rarity = determine_roll_rarity(player)
            is_personality = random.random() < 0.5
            
            if is_personality or rarity == "common":
                p_id = get_personality_of_rarity(rarity)
                p_name = PERSONAS_DB[p_id]["name"]
                unlocked = list(player.unlocked_personas or [])
                
                if p_id in unlocked:
                    shards_map = {"common": 1, "uncommon": 3, "rare": 10, "epic": 30, "legendary": 100}
                    shards_reward = shards_map.get(rarity, 1)
                    player.destiny_shards += shards_reward
                    results.append({
                        "type": "personality_duplicate",
                        "id": p_id,
                        "name": p_name,
                        "rarity": rarity,
                        "shards_reward": shards_reward,
                        "msg": f"Дубликат! {p_name} заменен на {shards_reward} осколков судьбы 🌟"
                    })
                else:
                    unlocked.append(p_id)
                    player.unlocked_personas = unlocked
                    results.append({
                        "type": "personality_new",
                        "id": p_id,
                        "name": p_name,
                        "rarity": rarity,
                        "msg": f"✨ НОВАЯ ЛИЧНОСТЬ: {p_name} ({rarity.upper()})!"
                    })
            else:
                items_pool = GACHA_ITEMS.get(rarity, ["gacha_luck_ring"])
                item_id = random.choice(items_pool)
                session.add(Equipment(player_id=player.id, item_id=item_id, durability=100, max_durability=100))
                results.append({
                    "type": "item",
                    "id": item_id,
                    "rarity": rarity,
                    "msg": f"📦 Выбит предмет: {item_id} ({rarity.upper()})!"
                })
                
        await session.commit()
        return {"status": "ok", "results": results, "shards": player.destiny_shards}
