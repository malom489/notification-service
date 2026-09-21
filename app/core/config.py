

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

    
    WORKER_ID: str = "worker-1"
    MAX_DELIVERY_ATTEMPTS: int = 3
    LOCK_TIMEOUT_SECONDS: int = 300  # 5 min: how long a worker can hold a job
    model_config=SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        case_sensitive=True,

      )
settings = Settings()
