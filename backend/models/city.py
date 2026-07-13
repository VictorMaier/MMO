from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Numeric
from sqlalchemy.orm import relationship
from database import Base

class City(Base):
    __tablename__ = 'cities'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    q = Column(Integer, nullable=False)
    r = Column(Integer, nullable=False)
    mayor_id = Column(Integer, ForeignKey('players.id', ondelete="SET NULL"), nullable=True)
    council_ids = Column(JSON, default=list)
    tax_rate = Column(Numeric(5, 2), default=5.00)
    market_tax_citizen = Column(Numeric(5, 2), default=5.00)
    market_tax_visitor = Column(Numeric(5, 2), default=10.00)
    craft_tax = Column(Numeric(5, 2), default=5.00)
    land_tax = Column(Numeric(5, 2), default=5.00)
    election_ends_at = Column(DateTime, nullable=True)
    wood = Column(Integer, default=1000)
    stone = Column(Integer, default=1000)
    iron = Column(Integer, default=500)
    coins = Column(Integer, default=0)
    mayor = relationship("Player", foreign_keys=[mayor_id])


class CityCandidate(Base):
    __tablename__ = 'city_candidates'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"))
    player_id = Column(Integer, ForeignKey('players.id', ondelete="CASCADE"))
    votes = Column(Integer, default=0)


class CityVote(Base):
    __tablename__ = 'city_votes'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"))
    player_id = Column(Integer, ForeignKey('players.id', ondelete="CASCADE"))


class Law(Base):
    __tablename__ = 'laws'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"))
    tax_type = Column(String, nullable=True)
    new_tax = Column(Integer, nullable=False)
    ends_at = Column(DateTime, nullable=False)
    status = Column(String, default="voting")
    votes_for = Column(Integer, default=0)
    votes_against = Column(Integer, default=0)


class LawVote(Base):
    __tablename__ = 'law_votes'
    id = Column(Integer, primary_key=True)
    law_id = Column(Integer, ForeignKey('laws.id', ondelete="CASCADE"))
    player_id = Column(Integer, ForeignKey('players.id', ondelete="CASCADE"))


class CityContract(Base):
    __tablename__ = 'city_contracts'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"))
    org_id = Column(Integer, ForeignKey('organizations.id', ondelete="SET NULL"), nullable=True)
    resource_type = Column(String, nullable=False)
    req_amount = Column(Integer, nullable=False)
    cur_amount = Column(Integer, default=0)
    reward_coins = Column(Integer, nullable=False)
    status = Column(String, default="open")
