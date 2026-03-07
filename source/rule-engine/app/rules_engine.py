from typing import List, Optional

from .actuators_client import ActuatorsClient
from .models import (
    ActuatorAction,
    Operator,
    Rule,
    UnifiedSensorEvent,
)


class RuleEngine:
    """
    - Keep rules in memory
    - Evaluate rules when UnifiedSensorEvent happens
    - Call actuators when rule satisfied
    """

    def __init__(self, actuators_client: Optional[ActuatorsClient] = None):
        self._rules: List[Rule] = []
        self._actuators = actuators_client or ActuatorsClient()

    # ----------------------
    # Manage rules in RAM
    # ----------------------

    def list_rules(self) -> List[Rule]:
        return list(self._rules)

    def add_rule(self, rule: Rule) -> Rule:
        # check for duplicates!
        self._rules.append(rule)
        return rule

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

    async def process_event(self, event: UnifiedSensorEvent) -> List[int]:
        """
        Given a sensor_id, check all active rules that refer it.
        For each satisfied rule, call actuator.
        Return all triggered rules.
        """
        triggered: List[int] = []

        for rule in self._rules:
            if not rule.is_active:
                continue
            if rule.sensor != event.sensor_id:
                continue

            value = self._find_measurement_value(event, rule)
            if value is None:
                continue

            if self._match_condition(value, rule):
                await self._actuators.set_state(rule.actuator, rule.action.value)
                triggered.append(rule.id)

        return triggered
