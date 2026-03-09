import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://mars_user:mars_password@localhost:5432/mars_db",
)