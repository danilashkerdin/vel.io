import json
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/velo_io"
    SECRET_KEY: str = "velo-io-default"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:8000"]'

    FREE_CAPTURES_LIMIT: int = 1
    FREE_PREMIUM_SLOTS: int = 30
    PREMIUM_PRICE_STARS: int = 200

    TON_MAINNET: bool = False
    TON_WALLET_ADDRESS: str = ""
    TON_API_KEY: str = ""

    ADMIN_EMAIL: str = "admin@vel.io"
    VIP_EMAILS: str = "[]"

    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_BOT_USERNAME: str = "velio_bot"

    FRONTEND_URL: str = "http://localhost:3000"
    APP_URL: str = "http://localhost:8000"

    SPONSORED_TIERS_JSON: str = (
        '[{"name":"Старт","stars":1000,"icon_size":32},'
        '{"name":"Стандарт","stars":3000,"icon_size":40},'
        '{"name":"Премиум","stars":5000,"icon_size":48}]'
    )

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sponsored_tiers(self):
        return json.loads(self.SPONSORED_TIERS_JSON)

    def is_vip(self, email: str) -> bool:
        try:
            vip_list = json.loads(self.VIP_EMAILS)
            return email in vip_list
        except (json.JSONDecodeError, TypeError):
            return False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
