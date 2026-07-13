import random

def get_exp_required(level):
    if level >= 100:
        return 999999999
    return int((100 * level) + ((level ** 2.2) * 2) + (50 * (level + 1)))

def calculate_crit(unit_state):
    crit_chance = min(75, max(5, unit_state.get("crit_chance", 5)))
    is_crit = random.random() < (crit_chance / 100.0)
    crit_mult = (unit_state.get("crit_damage", 150) / 100.0) if is_crit else 1.0
    return is_crit, crit_mult

def calculate_damage(attacker_state, defender_state, is_magic=False):
    is_crit, crit_mult = calculate_crit(attacker_state)
    
    if is_magic:
        base_dmg = attacker_state.get("magic_damage", attacker_state.get("damage", 10))
        defense = defender_state.get("magic_resist", 0)
    else:
        base_dmg = attacker_state.get("damage", 10)
        defense = defender_state.get("defense", 0)
        
    armor_pen = attacker_state.get("armor_pen", 0)
    effective_defense = max(0, defense * (1 - armor_pen / 100.0))
    
    damage_reduction = effective_defense / (effective_defense + 100.0) if (effective_defense + 100.0) != 0 else 0.0
    
    raw_damage = base_dmg * crit_mult
    final_damage = raw_damage * (1.0 - damage_reduction)
    
    min_damage = raw_damage * 0.1
    final_damage = max(min_damage, final_damage)
    
    return int(final_damage), is_crit

def calculate_initiative(unit_speed):
    randomness = random.uniform(-1.0, 1.0)
    return unit_speed + randomness
