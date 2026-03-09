# app/main.py
import time
from fastapi import FastAPI
from app.db.database import engine, Base
from app.api import rules
from sqlalchemy.exc import OperationalError

# Retry DB connection at startup so transient postgres start-up delays don't crash the service
for attempt in range(10):
    try:
        Base.metadata.create_all(bind=engine)
        break
    except OperationalError as e:
        if attempt == 9:
            raise
        print(f"[rules-service] DB not ready (attempt {attempt + 1}/10): {e}. Retrying in 3s…")
        time.sleep(3)

app = FastAPI(title="Mars Automation API")

# Registra il file delle rotte
app.include_router(rules.router)

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "rules-api"}