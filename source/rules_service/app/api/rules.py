# app/api/rules.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas.rule import RuleCreate, RuleResponse
from app.crud import rule as crud_rule

router = APIRouter(prefix="/api/rules", tags=["Rules"])

@router.post("/", response_model=RuleResponse, status_code=201)
def create_rule(rule: RuleCreate, db: Session = Depends(get_db)):
    return crud_rule.create_rule(db=db, rule=rule)

@router.get("/", response_model=List[RuleResponse])
def read_rules(db: Session = Depends(get_db)):
    return crud_rule.get_all_rules(db=db)

@router.patch("/actuator/{actuator_name}/disable", response_model=List[RuleResponse])
def disable_actuator_rules(actuator_name: str, db: Session = Depends(get_db)):
    """
    Disattiva tutte le regole associate a un attuatore specifico.
    Utile quando l'operatore prende il controllo manuale dal Frontend.
    """
    disabled_rules = crud_rule.disable_rules_by_actuator(db=db, actuator_name=actuator_name)
    return disabled_rules