from typing import Literal

import httpx
from fastapi import HTTPException

from .config import settings


class ActuatorsClient:
    """
      POST {ACTUATOR_BASE_URL}/{actuator_name}
      body: {"state": "ON" | "OFF"} [file:1]
    """

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.actuator_base_url

    async def set_state(self, actuator_name: str, state: Literal["ON", "OFF"]) -> None:
        url = f"{self.base_url}/{actuator_name}"
        payload = {"state": state}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Actuator service error: {response.status_code} {response.text}",
            )
