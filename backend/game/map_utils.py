import random
from heapq import heappush, heappop

DIRECTIONS = [(1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)]

BIOME_COSTS = {
    "forest": 2,
    "highland": 2,
    "mountain": 5,
    "steppe": 2,
    "swamp": 3,
    "city": 1
}

def hex_distance(q1, r1, q2, r2):
    return (abs(q1 - q2) + abs(q1 + r1 - q2 - r2) + abs(r1 - r2)) // 2

def get_hex_neighbors(q, r):
    return [(q + dq, r + dr) for dq, dr in DIRECTIONS]

def determine_albion_biome(height, moisture):
    if height > 0.7:
        return "mountain"
    elif height > 0.5:
        if moisture > 0.6:
            return "forest"
        else:
            return "highland"
    elif height > 0.3:
        if moisture > 0.7:
            return "forest"
        elif moisture > 0.4:
            return "steppe"
        else:
            return "steppe"
    else:
        if moisture > 0.5:
            return "swamp"
        else:
            return "steppe"

def a_star_road(start, end, cells_dict):
    open_set = []
    heappush(open_set, (0, start))
    came_from = {}
    g_score = {start: 0}
    
    while open_set:
        _, current = heappop(open_set)
        
        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]
            
        for neighbor in get_hex_neighbors(current[0], current[1]):
            if neighbor not in cells_dict:
                continue
                
            cell_biome = cells_dict[neighbor].biome
            weight = BIOME_COSTS.get(cell_biome, 2)
            tentative_g_score = g_score[current] + weight
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score = tentative_g_score + hex_distance(neighbor[0], neighbor[1], end[0], end[1])
                heappush(open_set, (f_score, neighbor))
                
    return []

def is_zone_more_dangerous(from_zone, to_zone):
    levels = {"green": 0, "yellow": 1, "red": 2}
    return levels.get(to_zone, 0) > levels.get(from_zone, 0)
