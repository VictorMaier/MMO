from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey
import datetime
from database import Base

class MarketOrder(Base):
    __tablename__ = 'market_orders'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"), nullable=False)
    creator_id = Column(BigInteger, nullable=False)
    creator_name = Column(String, nullable=False)
    order_type = Column(String, nullable=False)
    item_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    price_per_unit = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)


class MarketInbox(Base):
    __tablename__ = 'market_inboxes'
    id = Column(Integer, primary_key=True)
    player_id = Column(BigInteger, nullable=False)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"), nullable=False)
    item_id = Column(String, nullable=True)
    amount = Column(Integer, default=0)
    coins = Column(Integer, default=0)
    reason = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class MarketHistory(Base):
    __tablename__ = 'market_history'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"), nullable=False)
    item_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    price_per_unit = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
