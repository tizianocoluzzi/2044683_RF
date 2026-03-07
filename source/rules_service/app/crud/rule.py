# app/crud/rules.py
from sqlalchemy.orm import Session
from app.models.rule import RuleDB
from app.schemas.rule import RuleCreate

def create_rule(db: Session, rule: RuleCreate):
    db_rule = RuleDB(**rule.model_dump())
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule

def get_all_rules(db: Session):
    return db.query(RuleDB).all()