

from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings ,SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT_DIR / ".env")


class Settings(BaseSettings):
    

    PROJECT_NAME: str = "Notification Service"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"

    
    DATABASE_URL: str
    REDIS_URL: str
    SECRET_KEY: str
        # Email (Mailtrap Sandbox)
    SMTP_HOST: str = "sandbox.smtp.mailtrap.io"
    SMTP_PORT: int = 2525
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "notifications@notification-service.test"

    
    WORKER_ID: str = "worker-1"
    MAX_DELIVERY_ATTEMPTS: int = 3
    LOCK_TIMEOUT_SECONDS: int = 300 
    # 5 min: how long a worker can hold a job
    RETRY_BASE_DELAY_SECONDS: int=2
    RETRY_MAX_DELAY_SECONDS:int=300
    RETRY_JITTER_MAX_SECONDS:int=5
    model_config=SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        case_sensitive=True,

      )
settings = Settings()
