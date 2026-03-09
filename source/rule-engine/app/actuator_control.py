from typing import Dict, List

from .models import ActuatorMode


class ActuatorControlManager:
    """
    Keeps the control mode for each actuator:
    - AUTO: actuator follows rules
    - ON: actuator is manually forced ON
    - OFF: actuator is manually forced OFF
    """

    def __init__(self) -> None:
        self._modes: Dict[str, ActuatorMode] = {}

    def initialize(self, actuator_names: List[str]) -> None:
        self._modes = {name: ActuatorMode.AUTO for name in actuator_names}

    def has_actuator(self, actuator: str) -> bool:
        return actuator in self._modes

    def list_modes(self) -> Dict[str, str]:
        return {name: mode.value for name, mode in self._modes.items()}

    def get_mode(self, actuator: str) -> ActuatorMode:
        return self._modes.get(actuator, ActuatorMode.AUTO)

    def set_mode(self, actuator: str, mode: ActuatorMode) -> None:
        self._modes[actuator] = mode
