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

def disable_rules_by_actuator(db: Session, actuator_name: str):
    # Cerca tutte le regole attive per quell'attuatore specifico
    rules_to_disable = db.query(RuleDB).filter(
        RuleDB.actuator == actuator_name,
        RuleDB.is_active == True
    ).all()

    # Le spengo tutte
    for rule in rules_to_disable:
        rule.is_active = False

    # Salva le modifiche nel database se abbiamo trovato qualcosa
    if rules_to_disable:
        db.commit()

    return rules_to_disable

def update_rule(db: Session, rule_id: int, rule_data: dict):
    #cerca le regole
    db_rule = db.query(RuleDB).filter(RuleDB.id == rule_id).first()
    if db_rule:
        #aggiorna i campi con i nuovi valori
        for key, value in rule_data.items():
            setattr(db_rule, key, value)
        db.commit()
        db.refresh(db_rule)
    return db_rule

def delete_rule(db: Session, rule_id: int):
    db_rule = db.query(RuleDB).filter(RuleDB.id == rule_id).first()
    if db_rule:
        db.delete(db_rule)
        db.commit()
    return db_rule




