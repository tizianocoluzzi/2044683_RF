import os


class Settings:
    def __init__(self) -> None:
        self.service_name = "Rule Engine Service"
        
        self.actuator_base_url = os.getenv(
            "ACTUATOR_BASE_URL",
            "http://host.docker.internal:8080/api/actuators",
        )


settings = Settings()
