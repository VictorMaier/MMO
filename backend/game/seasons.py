from perlin_noise import PerlinNoise
from sqlalchemy import select
from database import async_session
from models import MapCell, City, ExpansionContract, Building
from game.map_utils import determine_albion_biome, hex_distance

MAP_RADIUS = 50

async def trigger_geological_shift():
    async with async_session() as session:
        await session.execute(ExpansionContract.__table__.delete())
        await session.execute(Building.__table__.delete())
        
        noise_elevation = PerlinNoise(octaves=4, seed=int(random_seed := int(random_seed_raw := 42 + 999 * (hash(datetime_hash := str(id)) % 1000) if 'id' in locals() else 55)))
        noise_moisture = PerlinNoise(octaves=4, seed=1337)
        
        cities = (await session.execute(select(City))).scalars().all()
        cells = (await session.execute(select(MapCell))).scalars().all()
        
        for cell in cells:
            if cell.is_city:
                continue
                
            x_val, y_val = cell.q / MAP_RADIUS, cell.r / MAP_RADIUS
            elevation = (noise_elevation([x_val, y_val]) + 1.0) / 2.0
            moisture = (noise_moisture([x_val, y_val]) + 1.0) / 2.0
            
            cell.biome = determine_albion_biome(elevation, moisture)
            cell.owner_org_id = None
            
            min_dist = 9999
            nearest_city_id = None
            for city in cities:
                dist = hex_distance(cell.q, cell.r, city.q, city.r)
                if dist < min_dist:
                    min_dist = dist
                    nearest_city_id = city.id
                    
            if min_dist <= 3:
                cell.risk_zone = "green"
                cell.controller_id = nearest_city_id
            elif min_dist <= 10:
                cell.risk_zone = "yellow"
                cell.controller_id = None
            else:
                cell.risk_zone = "red"
                cell.controller_id = None
                
        await session.commit()
