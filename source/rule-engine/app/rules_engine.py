import logging
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


logger = logging.getLogger(__name__)



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
        logger.info("RuleEngine initialized with actuators: %s", actuator_names)


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
        logger.info(
            "Received rule: id=%s sensor=%s metric=%s actuator=%s action=%s is_active=%s",
            rule.id,
            rule.sensor,
            rule.metric,
            rule.actuator,
            rule.action.value,
            rule.is_active,
        )


        existing_index = self._find_rule_index_by_id(rule.id)


        if not rule.is_active:
            if existing_index is not None:
                del self._rules[existing_index]
                logger.info("Rule removed: id=%s", rule.id)
                return "removed"
            logger.info("Rule ignored because inactive and not present: id=%s", rule.id)
            return "ignored"


        if existing_index is not None:
            self._rules[existing_index] = rule
            logger.info("Rule updated: id=%s", rule.id)
            return "updated"


        self._rules.append(rule)
        logger.info("Rule added: id=%s", rule.id)
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
        logger.info(
            "Matching start: rule_id=%s event_sensor=%s rule_sensor=%s rule_subsystem=%s rule_metric=%s groups=%s",
            rule.id,
            event.sensor_id,
            rule.sensor,
            rule.subsystem,
            rule.metric,
            len(event.metrics),
        )


        for group_index, group in enumerate(event.metrics):
            logger.info(
                "Matching group[%s]: subsystem=%s measurements_count=%s",
                group_index,
                getattr(group, "subsystem", None),
                len(group.measurements),
            )


            if rule.subsystem is not None:
                logger.info(
                    "Subsystem check: rule_subsystem=%s event_subsystem=%s",
                    rule.subsystem,
                    group.subsystem,
                )


                if group.subsystem != rule.subsystem:
                    logger.info(
                        "Group[%s] skipped: subsystem mismatch",
                        group_index,
                    )
                    continue


            for measure_index, m in enumerate(group.measurements):
                logger.info(
                    "Measurement[%s][%s]: metric=%s value=%s unit=%s",
                    group_index,
                    measure_index,
                    m.metric,
                    m.value,
                    getattr(m, "unit", None),
                )


                if m.metric != rule.metric:
                    logger.info(
                        "Measurement[%s][%s] skipped: metric mismatch (event=%s rule=%s)",
                        group_index,
                        measure_index,
                        m.metric,
                        rule.metric,
                    )
                    continue


                logger.info(
                    "Metric matched at group[%s] measurement[%s]: metric=%s raw_value=%s",
                    group_index,
                    measure_index,
                    m.metric,
                    m.value,
                )


                val = m.value
                try:
                    converted = float(val)
                    logger.info(
                        "Matching success: rule_id=%s converted_value=%s",
                        rule.id,
                        converted,
                    )
                    return converted
                except (ValueError, TypeError):
                    logger.info(
                        "Matching failed after metric match: non-numeric value=%s type=%s",
                        val,
                        type(val).__name__,
                    )
                    return None


        logger.info(
            "Matching failed: no compatible subsystem/metric found for rule_id=%s",
            rule.id,
        )
        return None



    async def set_actuator_mode(self, actuator: str, mode: ActuatorMode) -> None:
        self._actuator_controls.set_mode(actuator, mode)
        logger.info("Actuator mode changed: actuator=%s mode=%s", actuator, mode.value)


        if mode == ActuatorMode.ON:
            logger.info("Applying immediate manual override: actuator=%s state=ON", actuator)
            await self._actuators.set_state(actuator, "ON")
        elif mode == ActuatorMode.OFF:
            logger.info("Applying immediate manual override: actuator=%s state=OFF", actuator)
            await self._actuators.set_state(actuator, "OFF")
        else:
            logger.info("Actuator returned to AUTO mode: actuator=%s", actuator)


    


    async def process_event(self, event: UnifiedSensorEvent) -> List[int]:
        triggered_rules: List[int] = []


        logger.info(
            "Processing event: sensor_id=%s metrics_groups=%s active_rules=%s actuator_modes=%s",
            event.sensor_id,
            len(event.metrics),
            len(self._rules),
            self._actuator_controls.list_modes(),
        )


        for rule in self._rules:

            logger.info(
                "Rule pre-check: rule_id=%s rule_sensor=%s incoming_sensor=%s",
                rule.id,
                rule.sensor,
                event.sensor_id,
            )


            if rule.sensor != event.sensor_id:
                logger.info(
                    "Rule id=%s skipped before matching: sensor mismatch (rule=%s event=%s)",
                    rule.id,
                    rule.sensor,
                    event.sensor_id,
                )
                continue


            logger.info(
                "Checking rule id=%s for sensor=%s metric=%s actuator=%s",
                rule.id,
                rule.sensor,
                rule.metric,
                rule.actuator,
            )


            value = self._find_measurement_value(event, rule)
            if value is None:
                logger.info("Rule id=%s skipped: metric/subsystem not found in event", rule.id)
                continue


            logger.info(
                "Rule id=%s measurement found: event_value=%s operator=%s rule_value=%s",
                rule.id,
                value,
                rule.operator.value,
                rule.value,
            )


            if not self._match_condition(value, rule):
                logger.info("Rule id=%s condition not satisfied", rule.id)
                continue


            mode = self._actuator_controls.get_mode(rule.actuator)
            logger.info(
                "Actuator mode before command: actuator=%s mode=%s rule_action=%s",
                rule.actuator,
                mode.value,
                rule.action.value,
            )


            if mode == ActuatorMode.AUTO:
                desired_state = rule.action.value
            elif mode == ActuatorMode.ON:
                desired_state = "ON"
            else:
                desired_state = "OFF"


            logger.info(
                "Sending actuator command: actuator=%s desired_state=%s rule_id=%s",
                rule.actuator,
                desired_state,
                rule.id,
            )


            await self._actuators.set_state(rule.actuator, desired_state)


            logger.info(
                "Actuator command sent: actuator=%s final_state=%s rule_id=%s",
                rule.actuator,
                desired_state,
                rule.id,
            )


            triggered_rules.append(rule.id)


        logger.info(
            "Event processed: sensor_id=%s triggered_rules=%s actuator_modes=%s",
            event.sensor_id,
            triggered_rules,
            self._actuator_controls.list_modes(),
        )
        return triggered_rules
