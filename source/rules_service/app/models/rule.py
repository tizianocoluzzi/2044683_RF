from sqlalchemy import Column, Integer, String, Float, Boolean
from app.db.database import Base

class RuleDB(Base):
    __tablename__ = "rules"

    id = Column(Integer, primary_key=True, index=True)
    sensor = Column(String, index=True, nullable=False)
    metric = Column(String, nullable=False)
    subsystem = Column(String, nullable=True)
    operator = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    actuator = Column(String, nullable=False)
    action = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)