import os


class Settings:
    def __init__(self) -> None:
        self.service_name = "Rule Engine Service"
        self.actuator_base_url = os.getenv(
            "ACTUATOR_BASE_URL", 
            "http://base:8080/api/actuators" 
        )
        self.rabbitmq_url = os.getenv(
            "RABBITMQ_URL",
            "amqp://guest:guest@rabbitmq:5672/" 
        )


settings = Settings()
