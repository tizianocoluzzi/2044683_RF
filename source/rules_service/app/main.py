# app/main.py
from fastapi import FastAPI
from app.db.database import engine, Base
from app.api import rules

# Crea le tabelle nel DB all'avvio
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Mars Automation API")

# Registra il file delle rotte
app.include_router(rules.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "rules-api"}