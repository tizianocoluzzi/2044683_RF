from pydantic import BaseModel
from typing import Dict


class RestActuator(BaseModel):
    actuator_id: str
    state: str


class RestActuators(BaseModel):
    actuators: Dict[str, str]

    def to_list(self) -> list[RestActuator]:
        """Split the actuators map into one RestActuator per entry."""
        return [
            RestActuator(actuator_id=name, state=state)
            for name, state in self.actuators.items()
        ]
