import logging
from typing import Literal

import httpx
from fastapi import HTTPException

from .config import settings

logger = logging.getLogger(__name__)


class ActuatorsClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.actuator_base_url

    async def list_actuators(self) -> list[str]:
        async with httpx.AsyncClient() as client:
            response = await client.get(self.base_url)

        if response.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"Actuator service error: {response.status_code} {response.text}",
            )

        payload = response.json()
        logger.info("Actuators endpoint payload: %s", payload)

        if isinstance(payload, dict) and "actuators" in payload and isinstance(payload["actuators"], dict):
            actuators = payload["actuators"]
            names = list(actuators.keys())
            logger.info("Parsed actuators from nested payload: %s", names)
            return names

        if isinstance(payload, dict):
            names = list(payload.keys())
            logger.info("Parsed actuators from flat payload: %s", names)
            return names

        logger.warning("Unexpected actuators payload format: %s", type(payload))
        return []

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
