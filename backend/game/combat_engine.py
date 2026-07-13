import random
from game.formulas import calculate_damage, calculate_initiative

class CombatEngine:
    @staticmethod
    def initialize_battle(player, player_stats, monster_template):
        allies = [
            {
                "key": "ally_1",
                "id": player.id,
                "vk_id": player.vk_id,
                "name": f"Игрок #{player.vk_id}",
                "hp": player.current_hp,
                "max_hp": player_stats["max_hp"],
                "energy": player.energy,
                "max_energy": 100,
                "ap": 6,
                "speed": player_stats.get("speed", 5.0),
                "damage": player_stats["damage"],
                "defense": player_stats["defense"],
                "crit_chance": player_stats.get("crit_chance", 5),
                "crit_damage": player_stats.get("crit_damage", 150),
                "armor_pen": player_stats.get("armor_pen", 0),
                "statuses": []
            }
        ]
        
        enemies = [
            {
                "key": "enemy_1",
                "name": monster_template["name"],
                "hp": monster_template["hp"],
                "max_hp": monster_template["hp"],
                "energy": 100,
                "max_energy": 100,
                "ap": 4,
                "speed": monster_template.get("speed", 4.0),
                "damage": monster_template["damage"],
                "defense": monster_template["defense"],
                "crit_chance": 5,
                "crit_damage": 150,
                "armor_pen": 0,
                "statuses": []
            }
        ]
        
        state = {
            "round": 1,
            "current_turn_index": 0,
            "turn_order": [],
            "allies": allies,
            "enemies": enemies,
            "action_log": ["Бой начался!"]
        }
        
        CombatEngine.recalculate_turn_order(state)
        CombatEngine.start_turn(state)
        return state

    @staticmethod
    def recalculate_turn_order(state):
        units = []
        for a in state["allies"]:
            if a["hp"] > 0:
                units.append((a["key"], calculate_initiative(a["speed"])))
        for e in state["enemies"]:
            if e["hp"] > 0:
                units.append((e["key"], calculate_initiative(e["speed"])))
                
        units.sort(key=lambda x: x[1], reverse=True)
        state["turn_order"] = [u[0] for u in units]

    @staticmethod
    def find_unit(state, key):
        for a in state["allies"]:
            if a["key"] == key:
                return a
        for e in state["enemies"]:
            if e["key"] == key:
                return e
        return None

    @staticmethod
    def start_turn(state):
        if not state["turn_order"]:
            return
        
        active_key = state["turn_order"][state["current_turn_index"]]
        unit = CombatEngine.find_unit(state, active_key)
        if not unit or unit["hp"] <= 0:
            return
            
        unit["ap"] = 6
        unit["energy"] = min(unit["max_energy"], unit["energy"] + 10)
        
        active_statuses = []
        is_stunned = False
        
        for status in unit.get("statuses", []):
            status["duration"] -= 1
            status_type = status["type"]
            
            if status_type == "bleed":
                damage = status["value"]
                unit["hp"] = max(0, unit["hp"] - damage)
                state["action_log"].append(f"{unit['name']} теряет {damage} HP от кровотечения!")
            elif status_type == "poison":
                damage = status["value"]
                unit["hp"] = max(0, unit["hp"] - damage)
                state["action_log"].append(f"{unit['name']} теряет {damage} HP от яда!")
            elif status_type == "stun":
                is_stunned = True
                
            if status["duration"] > 0:
                active_statuses.append(status)
                
        unit["statuses"] = active_statuses
        
        if is_stunned:
            state["action_log"].append(f"{unit['name']} оглушен и пропускает ход!")
            unit["ap"] = 0

    @staticmethod
    def execute_action(state, action_type, target_key, item_id=None, skill_id=None):
        active_key = state["turn_order"][state["current_turn_index"]]
        attacker = CombatEngine.find_unit(state, active_key)
        defender = CombatEngine.find_unit(state, target_key)
        
        if not attacker or attacker["hp"] <= 0:
            return False
            
        if action_type == "attack":
            if attacker["ap"] < 2:
                return False
            
            if not defender or defender["hp"] <= 0:
                return False
                
            attacker["ap"] -= 2
            
            damage, is_crit = calculate_damage(attacker, defender)
            defender["hp"] = max(0, defender["hp"] - damage)
            
            crit_text = " КРИТ!" if is_crit else ""
            state["action_log"].append(f"{attacker['name']} атакует {defender['name']} на {damage} урона!{crit_text}")
            
            if defender["hp"] <= 0:
                state["action_log"].append(f"{defender['name']} повержен!")
            return True
            
        elif action_type == "skip":
            attacker["ap"] = 0
            state["action_log"].append(f"{attacker['name']} пропускает оставшуюся часть хода.")
            return True
            
        return False

    @staticmethod
    def ai_decide_action(state):
        active_key = state["turn_order"][state["current_turn_index"]]
        attacker = CombatEngine.find_unit(state, active_key)
        if not attacker or attacker["hp"] <= 0:
            return
            
        while attacker["ap"] >= 2:
            living_allies = [a for a in state["allies"] if a["hp"] > 0]
            if not living_allies:
                break
                
            target = random.choice(living_allies)
            success = CombatEngine.execute_action(state, "attack", target["key"])
            
            if not success:
                attacker["ap"] = 0
                state["action_log"].append(f"{attacker['name']} в замешательстве и завершает ход.")
                break

    @staticmethod
    def next_turn(state):
        state["current_turn_index"] += 1
        if state["current_turn_index"] >= len(state["turn_order"]):
            state["current_turn_index"] = 0
            state["round"] += 1
            state["action_log"].append(f"--- Раунд {state['round']} ---")
            CombatEngine.recalculate_turn_order(state)
            
        CombatEngine.start_turn(state)
