from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Organization(Base):
    __tablename__ = 'organizations'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"), nullable=True)
    name = Column(String, nullable=False)
    master_id = Column(Integer, ForeignKey('players.id'), nullable=True)
    wood = Column(Integer, default=0)
    stone = Column(Integer, default=0)
    iron = Column(Integer, default=0)
    fiber = Column(Integer, default=0)
    hide = Column(Integer, default=0)
    food = Column(Integer, default=0)
    essence = Column(Integer, default=0)
    coins = Column(Integer, default=0)
    members = relationship("Player", back_populates="organization", foreign_keys="Player.organization_id")
