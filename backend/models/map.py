from sqlalchemy import Column, Integer, String, Boolean, UniqueConstraint, ForeignKey, Numeric, DateTime, JSON
from database import Base

class MapCell(Base):
    __tablename__ = 'map_cells'
    id = Column(Integer, primary_key=True)
    q = Column(Integer, nullable=False)
    r = Column(Integer, nullable=False)
    biome = Column(String, nullable=False)
    height = Column(Numeric(3, 2), default=0.0)
    moisture = Column(Numeric(3, 2), default=0.0)
    risk_zone = Column(String, nullable=False)
    is_city = Column(Boolean, default=False)
    has_road = Column(Boolean, default=False)
    near_water = Column(Boolean, default=False)
    has_river = Column(Boolean, default=False)
    controller_id = Column(Integer, ForeignKey('cities.id', ondelete="SET NULL"), nullable=True)
    owner_org_id = Column(Integer, ForeignKey('organizations.id', ondelete="SET NULL"), nullable=True)
    
    __table_args__ = (UniqueConstraint('q', 'r', name='_q_r_uc_new'),)


class ExpansionContract(Base):
    __tablename__ = 'expansion_contracts'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"))
    target_cell_id = Column(Integer, ForeignKey('map_cells.id', ondelete="CASCADE"))
    organization_id = Column(Integer, ForeignKey('organizations.id', ondelete="CASCADE"))
    flag_placed_at = Column(DateTime, nullable=True)
    capture_progress = Column(Integer, default=0)
    required_time = Column(Integer, default=48)
    status = Column(String, default="pending")
    reward_coins = Column(Integer, nullable=True)
    reward_resources = Column(JSON, nullable=True)


class Building(Base):
    __tablename__ = 'buildings'
    id = Column(Integer, primary_key=True)
    city_id = Column(Integer, ForeignKey('cities.id', ondelete="CASCADE"), nullable=True)
    cell_id = Column(Integer, ForeignKey('map_cells.id', ondelete="CASCADE"), nullable=True)
    building_type = Column(String, nullable=False)
    level = Column(Integer, default=1)
    hp = Column(Integer, default=100)
    max_hp = Column(Integer, default=100)
