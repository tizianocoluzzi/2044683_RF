from typing import List, Optional

from .actuators_client import ActuatorsClient
from .models import (
    ActuatorMode,
    ActuatorAction,
    Operator,
    Rule,
    UnifiedSensorEvent,
)
from .actuator_control import ActuatorControlManager

class RuleEngine:
    """
    - Keep rules in memory
    - Evaluate rules when UnifiedSensorEvent happens
    - Call actuators when rule satisfied
    """
    def __init__(
        self,
        actuators_client: Optional[ActuatorsClient] = None,
        actuator_control_manager: Optional[ActuatorControlManager] = None,
    ):
        self._rules: List[Rule] = []
        self._actuators = actuators_client or ActuatorsClient()
        self._actuator_controls = actuator_control_manager or ActuatorControlManager()

    async def initialize(self) -> None:
        actuator_names = await self._actuators.list_actuators()
        self._actuator_controls.initialize(actuator_names)


    # ----------------------
    # Manage rules in RAM
    # ----------------------

    def list_rules(self) -> List[Rule]:
        return list(self._rules)
    
    def list_actuator_modes(self) -> dict[str, str]:
        return self._actuator_controls.list_modes()
    
    def has_actuator(self, actuator: str) -> bool:
        return self._actuator_controls.has_actuator(actuator)
    
    def _find_rule_index_by_id(self, rule_id: int) -> Optional[int]:
        for index, existing_rule in enumerate(self._rules):
            if existing_rule.id == rule_id:
                return index
        return None

    def add_rule(self, rule: Rule) -> str:
        """
        Add, update, ignore, or remove a rule based on its id and is_active flag.

        Behavior:
        - inactive + not present  -> ignore
        - inactive + present      -> remove
        - active + not present    -> add
        - active + present        -> update
        """
        existing_index = self._find_rule_index_by_id(rule.id)

        if not rule.is_active:
            if existing_index is not None:
                del self._rules[existing_index]
                return "removed"
            return "ignored"

        if existing_index is not None:
            self._rules[existing_index] = rule
            return "updated"

        self._rules.append(rule)
        return "added"

    # --------------------------
    # Evaluation functions
    # --------------------------

    @staticmethod
    def _match_condition(sensor_value: float, rule: Rule) -> bool:
        if rule.operator == Operator.gt:
            return sensor_value > rule.value
        if rule.operator == Operator.lt:
            return sensor_value < rule.value
        if rule.operator == Operator.eq:
            return sensor_value == rule.value
        return False

    @staticmethod
    def _find_measurement_value(event: UnifiedSensorEvent, rule: Rule) -> Optional[float]:
        """
        Given a sensor value, check if its metric matches with
        one saved in the rules, return the rule's value if that's true
        """
        for group in event.metrics:
            if rule.subsystem is not None and group.subsystem != rule.subsystem:
                continue

            for m in group.measurements:
                if m.metric != rule.metric:
                    continue

                val = m.value
                try:
                    return float(val)
                except (ValueError, TypeError):
                    return None

        return None

    async def set_actuator_mode(self, actuator: str, mode: ActuatorMode) -> None:
        self._actuator_controls.set_mode(actuator, mode)

        if mode == ActuatorMode.ON:
            await self._actuators.set_state(actuator, "ON")
        elif mode == ActuatorMode.OFF:
            await self._actuators.set_state(actuator, "OFF")

    async def process_event(self, event: UnifiedSensorEvent) -> List[int]:
        triggered_rules: List[int] = []

        for rule in self._rules:
            if rule.sensor != event.sensor_id:
                continue

            value = self._find_measurement_value(event, rule)
            if value is None:
                continue

            if not self._match_condition(value, rule):
                continue

            mode = self._actuator_controls.get_mode(rule.actuator)

            if mode == ActuatorMode.AUTO:
                desired_state = rule.action.value
            elif mode == ActuatorMode.ON:
                desired_state = "ON"
            else:
                desired_state = "OFF"

            await self._actuators.set_state(rule.actuator, desired_state)
            triggered_rules.append(rule.id)

        return triggered_rules
