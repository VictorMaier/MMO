import os
import json
import asyncio
import aiohttp
import random
from database import async_session
from sqlalchemy import select
from models.player import Player
from models.city import City

VK_TOKEN = os.getenv("BOT_TOKEN", "your_vk_token_here")
APP_ID = 54664572

async def get_vk_api(session: aiohttp.ClientSession, method: str, params: dict):
    params['access_token'] = VK_TOKEN
    params['v'] = '5.199'
    async with session.post(f"https://api.vk.com/method/{method}", data=params) as resp:
        return await resp.json()

async def send_bot_notification(vk_id: int, text: str):
    async with aiohttp.ClientSession() as session:
        await get_vk_api(session, "messages.send", {
            "user_id": vk_id,
            "message": text,
            "random_id": random.randint(-2147483648, 2147483647)
        })

async def run_vk_bot():
    async with aiohttp.ClientSession() as session:
        group_info = await get_vk_api(session, "groups.getById", {})
        if "error" in group_info:
            print(f"VK API Error: {group_info['error']}")
            return
        group_id = group_info['response'][0]['id']

        lp_info = await get_vk_api(session, "groups.getLongPollServer", {"group_id": group_id})
        if "error" in lp_info:
            print(f"VK LongPoll Error: {lp_info['error']}")
            return
        
        server = lp_info['response']['server']
        key = lp_info['response']['key']
        ts = lp_info['response']['ts']

        print(f"VK LongPoll успешно запущен для группы {group_id}")

        while True:
            try:
                async with session.get(f"{server}?act=a_check&key={key}&ts={ts}&wait=25", timeout=30) as resp:
                    data = await resp.json()
                    
                    if 'failed' in data:
                        lp_info = await get_vk_api(session, "groups.getLongPollServer", {"group_id": group_id})
                        server = lp_info['response']['server']
                        key = lp_info['response']['key']
                        ts = lp_info['response']['ts']
                        continue
                        
                    ts = data['ts']
                    for update in data.get('updates', []):
                        if update['type'] == 'message_new':
                            msg = update['object']['message']
                            text = msg.get('text', '').lower()
                            from_id = msg.get('from_id')
                            
                            if text in ['/start', '/map', 'начать', 'старт', 'карта']:
                                async with async_session() as db_session:
                                    player = (await db_session.execute(select(Player).where(Player.vk_id == from_id))).scalars().first()
                                    if not player:
                                        cities = (await db_session.execute(select(City))).scalars().all()
                                        start_city = random.choice(cities) if cities else None
                                        q, r = (start_city.q, start_city.r) if start_city else (0, 0)
                                        c_id = start_city.id if start_city else None
                                        
                                        player = Player(
                                            vk_id=from_id, q=q, r=r,
                                            citizenship_city_id=c_id, citizenship_status="citizen",
                                            disabled_warnings=[]
                                        )
                                        db_session.add(player)
                                        await db_session.commit()
                                        
                                keyboard = {
                                    "inline": True,
                                    "buttons": [[{
                                        "action": {
                                            "type": "open_app",
                                            "app_id": APP_ID,
                                            "label": "Открыть игру 🏰",
                                            "hash": ""
                                        }
                                    }]]
                                }
                                
                                await get_vk_api(session, "messages.send", {
                                    "user_id": from_id,
                                    "message": "Добро пожаловать в MMO WebApp! Нажмите на кнопку ниже, чтобы войти в игру.",
                                    "keyboard": json.dumps(keyboard),
                                    "random_id": random.randint(-2147483648, 2147483647)
                                })
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"LongPoll Error: {e}")
                await asyncio.sleep(5)
