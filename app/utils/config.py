# app/utils/config.py

import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    # MongoDB
    mongodb_uri: str = os.getenv("MONGODB_URI")
    
    # RabbitMQ
    rabbitmq_host: str = os.getenv("RABBITMQ_HOST")
    rabbitmq_port: int = int(os.getenv("RABBITMQ_PORT", 5672))
    rabbitmq_user: str = os.getenv("RABBITMQ_USER")
    rabbitmq_password: str = os.getenv("RABBITMQ_PASSWORD")
    rabbitmq_queue: str = os.getenv("RABBITMQ_QUEUE")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "DEBUG")

    class Config:
        env_file = ".env"

settings = Settings()