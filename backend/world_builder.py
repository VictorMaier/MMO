import asyncio
import math
from perlin_noise import PerlinNoise
from database import engine, Base, async_session
from models.map import MapCell
from models.city import City
from game.map_utils import determine_albion_biome, a_star_road, hex_distance

MAP_RADIUS = 50

async def build_world():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    noise_elevation = PerlinNoise(octaves=4, seed=42)
    noise_moisture = PerlinNoise(octaves=4, seed=1337)

    cells_dict = {}
    
    for q in range(-MAP_RADIUS, MAP_RADIUS + 1):
        for r in range(-MAP_RADIUS, MAP_RADIUS + 1):
            if (abs(q) + abs(q + r) + abs(r)) // 2 <= MAP_RADIUS:
                x_val, y_val = q / MAP_RADIUS, r / MAP_RADIUS
                elevation = (noise_elevation([x_val, y_val]) + 1.0) / 2.0
                moisture = (noise_moisture([x_val, y_val]) + 1.0) / 2.0
                
                biome = determine_albion_biome(elevation, moisture)
                
                cells_dict[(q, r)] = MapCell(
                    q=q, r=r, biome=biome, 
                    height=elevation, moisture=moisture,
                    risk_zone="red", has_road=False
                )

    cities_to_insert = []
    city_radius = int(MAP_RADIUS * 0.6)
    
    for i in range(5):
        angle = math.radians(72 * i)
        cq, cr = int(city_radius * math.cos(angle)), int(city_radius * math.sin(angle))
        cities_to_insert.append(City(name=f"Город {i+1}", q=cq, r=cr))
        
        if (cq, cr) in cells_dict:
            cells_dict[(cq, cr)].biome = "city"
            cells_dict[(cq, cr)].is_city = True

    for i in range(5):
        start_city = cities_to_insert[i]
        end_city = cities_to_insert[(i + 1) % 5]
        road_path = a_star_road((start_city.q, start_city.r), (end_city.q, end_city.r), cells_dict)
        for (q, r) in road_path:
            if (q, r) in cells_dict:
                cells_dict[(q, r)].has_road = True

    for (q, r), cell in cells_dict.items():
        min_dist = 9999
        nearest_city_id = None
        for i, city in enumerate(cities_to_insert, start=1):
            dist = hex_distance(q, r, city.q, city.r)
            if dist < min_dist:
                min_dist = dist
                nearest_city_id = i
                
        if min_dist <= 3:
            cell.risk_zone = "green"
            cell.controller_id = nearest_city_id
        elif min_dist <= 10:
            cell.risk_zone = "yellow"
        else:
            cell.risk_zone = "red"

    async with async_session() as session:
        session.add_all(cells_dict.values())
        session.add_all(cities_to_insert)
        await session.commit()

if __name__ == "__main__":
    asyncio.run(build_world())
