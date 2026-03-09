# app/api/rules.py
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas.rule import RuleCreate, RuleResponse
from app.crud import rule as crud_rule
import requests

router = APIRouter(prefix="/api/rules", tags=["Rules"])

ENGINE_URL = "http://localhost:8000/rules"

def send_rules_to_engine(rules_data):
    """Invia le regole aggiornate all'altro microservizio"""
    try:
        # Trasforma i dati in formato JSON per l'invio
        # Usa timeout=5 per non bloccare tutto se l'altro servizio è morto
        response = requests.post(ENGINE_URL, json=rules_data, timeout=5)
        response.raise_for_status()
        print(f" Regole inviate con successo al motore! Status: {response.status_code}")
    except Exception as e:
        print(f" Errore nell'invio delle regole al motore: {e}")


@router.post("/", response_model=RuleResponse, status_code=201)
def create_rule(
        rule: RuleCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    # 1. Salva nel DB
    db_rule = crud_rule.create_rule(db, rule)

    # 2. Mettiamo la singola regola in una lista e la trasformiamo in JSON
    # Il risultato sarà: [ { "id": 1, "sensor": "...", ... } ]
    rule_data = jsonable_encoder([db_rule])

    background_tasks.add_task(send_rules_to_engine, rule_data)

    # 3. Rispondi subito al frontend
    return db_rule

@router.get("/", response_model=List[RuleResponse])
def read_rules(db: Session = Depends(get_db)):
    return crud_rule.get_all_rules(db=db)


@router.patch("/actuator/{actuator_name}/disable", response_model=List[RuleResponse])
def disable_actuator_rules(
        actuator_name: str,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db)
):
    # 1. Disattiva nel DB
    disabled_rules = crud_rule.disable_rules_by_actuator(db=db, actuator_name=actuator_name)

    # 2. Se abbiamo disattivato qualcosa, manda la lista completa
    if disabled_rules:
        rules_data = jsonable_encoder(disabled_rules)
        background_tasks.add_task(send_rules_to_engine, rules_data)

    # 3. Rispondi al frontend
    return disabled_rules