import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_
from database import async_session
from models import Player, City, MarketOrder, MarketInbox, MarketHistory, Equipment

router = APIRouter()

class OrderCreateReq(BaseModel):
    vk_id: int
    order_type: str
    item_id: str
    amount: int
    price_per_unit: int

class OrderFulfillReq(BaseModel):
    vk_id: int
    order_id: int
    amount: int

class CancelOrderReq(BaseModel):
    vk_id: int
    order_id: int

class ClaimInboxReq(BaseModel):
    vk_id: int
    claim_id: int

@router.get("/api/market/list")
async def get_market_list(vk_id: int, order_type: str = "sell", page: int = 1):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == vk_id))).scalars().first()
        city = (await session.execute(select(City).where(and_(City.q == player.q, City.r == player.r)))).scalars().first()
        if not city:
            raise HTTPException(status_code=400, detail="Рынок доступен только в городах")
            
        stmt = select(MarketOrder).where(and_(MarketOrder.city_id == city.id, MarketOrder.order_type == order_type))
        if order_type == "sell":
            stmt = stmt.order_by(MarketOrder.price_per_unit.asc())
        else:
            stmt = stmt.order_by(MarketOrder.price_per_unit.desc())
            
        orders = (await session.execute(stmt.offset((page - 1) * 5).limit(5))).scalars().all()
        return {
            "orders": [
                {
                    "id": o.id,
                    "creator_name": o.creator_name,
                    "item_id": o.item_id,
                    "amount": o.amount,
                    "price": o.price_per_unit
                } for o in orders
            ],
            "total_pages": 1
        }

@router.get("/api/market/my_orders")
async def get_my_orders(vk_id: int):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == vk_id))).scalars().first()
        city = (await session.execute(select(City).where(and_(City.q == player.q, City.r == player.r)))).scalars().first()
        if not city:
            return []
        orders = (await session.execute(
            select(MarketOrder).where(and_(MarketOrder.city_id == city.id, MarketOrder.creator_id == vk_id))
        )).scalars().all()
        return [
            {
                "id": o.id,
                "order_type": o.order_type,
                "item_id": o.item_id,
                "amount": o.amount,
                "price": o.price_per_unit
            } for o in orders
        ]

@router.get("/api/market/inbox")
async def get_market_inbox(vk_id: int):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == vk_id))).scalars().first()
        inboxes = (await session.execute(
            select(MarketInbox).where(MarketInbox.player_id == player.id)
        )).scalars().all()
        return [
            {
                "id": i.id,
                "item_id": i.item_id,
                "amount": i.amount,
                "coins": i.coins,
                "reason": i.reason
            } for i in inboxes
        ]

@router.post("/api/market/create")
async def create_market_order(req: OrderCreateReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        city = (await session.execute(select(City).where(and_(City.q == player.q, City.r == player.r)))).scalars().first()
        if not city:
            raise HTTPException(status_code=400, detail="Создание ордеров доступно только в городах")
            
        if req.amount < 1 or req.price_per_unit < 1:
            raise HTTPException(status_code=400, detail="Неверные данные")
            
        setup_fee = max(1, int((req.amount * req.price_per_unit) * 0.025))
        if player.coins < setup_fee:
            raise HTTPException(status_code=400, detail=f"Недостаточно монет для пошлины: {setup_fee} 🪙")
            
        if req.order_type == "sell":
            if req.item_id in ["wood", "stone", "iron", "fiber", "hide", "food"]:
                if getattr(player, req.item_id) < req.amount:
                    raise HTTPException(status_code=400, detail="Недостаточно ресурсов")
                setattr(player, req.item_id, getattr(player, req.item_id) - req.amount)
            else:
                eqs = (await session.execute(
                    select(Equipment).where(and_(Equipment.player_id == player.id, Equipment.item_id == req.item_id, Equipment.is_equipped == False))
                )).scalars().all()
                if len(eqs) < req.amount:
                    raise HTTPException(status_code=400, detail="Недостаточно свободных предметов")
                for i in range(req.amount):
                    await session.delete(eqs[i])
            player.coins -= setup_fee
        else:
            total_cost = (req.amount * req.price_per_unit) + setup_fee
            if player.coins < total_cost:
                raise HTTPException(status_code=400, detail=f"Необходимо {total_cost} 🪙")
            player.coins -= total_cost
            
        expires = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
        order = MarketOrder(
            city_id=city.id,
            creator_id=player.vk_id,
            creator_name=f"Игрок {player.vk_id}",
            order_type=req.order_type,
            item_id=req.item_id,
            amount=req.amount,
            price_per_unit=req.price_per_unit,
            expires_at=expires
        )
        session.add(order)
        await session.commit()
        return {"status": "ok", "message": f"Ордер создан! Списана пошлина {setup_fee} 🪙"}

@router.post("/api/market/fulfill")
async def fulfill_market_order(req: OrderFulfillReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        order = (await session.execute(select(MarketOrder).where(MarketOrder.id == req.order_id))).scalars().first()
        if not order or order.amount < req.amount or req.amount <= 0:
            raise HTTPException(status_code=400, detail="Ордер не найден или объем некорректен")
            
        city = (await session.execute(select(City).where(City.id == order.city_id))).scalars().first()
        is_citizen = player.citizenship_city_id == city.id and player.citizenship_status == "citizen"
        
        tax_rate = city.market_tax_citizen if is_citizen else city.market_tax_visitor
        total_price = req.amount * order.price_per_unit
        tax = int(total_price * (float(tax_rate) / 100.0))
        seller_receive = total_price - tax
        
        if order.order_type == "sell":
            if player.coins < total_price:
                raise HTTPException(status_code=400, detail="Недостаточно монет")
            player.coins -= total_price
            
            if order.item_id in ["wood", "stone", "iron", "fiber", "hide", "food"]:
                setattr(player, order.item_id, getattr(player, order.item_id) + req.amount)
            else:
                for _ in range(req.amount):
                    session.add(Equipment(player_id=player.id, item_id=order.item_id))
                    
            city.coins += tax
            session.add(MarketInbox(player_id=order.creator_id, city_id=city.id, coins=seller_receive, reason="Продажа лота"))
        else:
            if order.item_id in ["wood", "stone", "iron", "fiber", "hide", "food"]:
                if getattr(player, order.item_id) < req.amount:
                    raise HTTPException(status_code=400, detail="Недостаточно ресурсов")
                setattr(player, order.item_id, getattr(player, order.item_id) - req.amount)
            else:
                eqs = (await session.execute(
                    select(Equipment).where(and_(Equipment.player_id == player.id, Equipment.item_id == order.item_id, Equipment.is_equipped == False))
                )).scalars().all()
                if len(eqs) < req.amount:
                    raise HTTPException(status_code=400, detail="Недостаточно предметов для продажи")
                for i in range(req.amount):
                    await session.delete(eqs[i])
                    
            player.coins += seller_receive
            city.coins += tax
            session.add(MarketInbox(player_id=order.creator_id, city_id=city.id, item_id=order.item_id, amount=req.amount, reason="Выкуп ордера"))
            
        order.amount -= req.amount
        session.add(MarketHistory(city_id=city.id, item_id=order.item_id, amount=req.amount, price_per_unit=order.price_per_unit))
        
        if order.amount <= 0:
            await session.delete(order)
            
        await session.commit()
        return {"status": "ok", "message": "Сделка успешно завершена!"}

@router.post("/api/market/cancel")
async def cancel_market_order(req: CancelOrderReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        order = (await session.execute(select(MarketOrder).where(MarketOrder.id == req.order_id))).scalars().first()
        if not order:
            raise HTTPException(status_code=404)
        if order.creator_id != player.vk_id:
            raise HTTPException(status_code=403)
            
        if order.order_type == "sell":
            session.add(MarketInbox(player_id=player.id, city_id=order.city_id, item_id=order.item_id, amount=order.amount, reason="Отмена продажи"))
        else:
            refund = order.amount * order.price_per_unit
            session.add(MarketInbox(player_id=player.id, city_id=order.city_id, coins=refund, reason="Отмена покупки"))
            
        await session.delete(order)
        await session.commit()
        return {"status": "ok"}

@router.post("/api/market/claim")
async def claim_market_inbox(req: ClaimInboxReq):
    async with async_session() as session:
        player = (await session.execute(select(Player).where(Player.vk_id == req.vk_id))).scalars().first()
        inbox = (await session.execute(
            select(MarketInbox).where(and_(MarketInbox.id == req.claim_id, MarketInbox.player_id == player.id))
        )).scalars().first()
        if not inbox:
            raise HTTPException(status_code=404)
            
        if inbox.coins > 0:
            player.coins += inbox.coins
        if inbox.item_id:
            if inbox.item_id in ["wood", "stone", "iron", "fiber", "hide", "food"]:
                setattr(player, inbox.item_id, getattr(player, inbox.item_id) + inbox.amount)
            else:
                for _ in range(box_amount := inbox.amount):
                    session.add(Equipment(player_id=player.id, item_id=inbox.item_id))
                    
        await session.delete(inbox)
        await session.commit()
        return {"status": "ok"}
