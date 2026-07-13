from sqlalchemy import Column, Integer, BigInteger, String, Boolean, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship
from database import Base

class Player(Base):
    __tablename__ = 'players'
    id = Column(Integer, primary_key=True)
    vk_id = Column(BigInteger, unique=True, nullable=False)
    q = Column(Integer, default=0)
    r = Column(Integer, default=0)
    energy = Column(Integer, default=100)
    current_hp = Column(Integer, default=100)
    wood = Column(Integer, default=0)
    stone = Column(Integer, default=0)
    iron = Column(Integer, default=0)
    fiber = Column(Integer, default=0)
    hide = Column(Integer, default=0)
    food = Column(Integer, default=0)
    coins = Column(Integer, default=500)
    essence = Column(Integer, default=0)
    unlocked_personas = Column(JSON, default=list)
    active_personas = Column(JSON, default=list)
    skills = Column(JSON, default=dict)
    is_wayfarer = Column(Boolean, default=True)
    disabled_warnings = Column(JSON, default=list)
    gacha_pity_10 = Column(Integer, default=0)
    gacha_pity_90 = Column(Integer, default=0)
    destiny_shards = Column(Integer, default=0)
    
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete="SET NULL"), nullable=True)
    org_role = Column(String, default="none")
    organization = relationship("Organization", back_populates="members", foreign_keys=[organization_id])
    
    citizenship_city_id = Column(Integer, ForeignKey('cities.id', ondelete="SET NULL"), nullable=True)
    citizenship_status = Column(String, default="citizen")
    citizenship_timer = Column(DateTime, nullable=True)

    equipment = relationship("Equipment", back_populates="owner")
    combat = relationship("Combat", back_populates="player", uselist=False)


class Equipment(Base):
    __tablename__ = 'equipment'
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id', ondelete="CASCADE"))
    item_id = Column(String, nullable=False)
    is_equipped = Column(Boolean, default=False)
    durability = Column(Integer, default=100)
    max_durability = Column(Integer, default=100)
    enchant_level = Column(Integer, default=0)
    owner = relationship("Player", back_populates="equipment")


class Combat(Base):
    __tablename__ = 'combats'
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, ForeignKey('players.id', ondelete="CASCADE"), unique=True)
    combat_state = Column(JSON, nullable=False)
    player = relationship("Player", back_populates="combat")
