import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.resolve()


class Settings(BaseSettings):
    # ExpiredDomains.net
    expired_username: str = ""
    expired_password: str = ""

    # AI Provider: "gemini" or "openai"
    ai_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # SMTP Gmail
    smtp_server: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    email_to: str = ""
    email_cc: str = ""

    # Scheduling
    daily_run_hour: int = 8
    daily_run_minute: int = 0

    # Scraping
    scrape_pages: int = 3
    sort_column: str = "bl"
    max_domains_to_analyze: int = 200
    top_n_domains: int = 20

    # AI Scoring
    ai_scoring_enabled: bool = True
    ai_scoring_batch_size: int = 5
    ai_scoring_timeout: int = 30

    # Paths
    excel_output_dir: str = "reports"
    database_path: str = "data/domains.db"
    log_level: str = "INFO"
    log_file: str = "data/agent.log"

    # URLs
    login_url: str = "https://www.expireddomains.net/login/"
    target_base: str = "https://member.expireddomains.net/domains/expiredcom/"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def excel_dir(self) -> Path:
        p = PROJECT_ROOT / self.excel_output_dir
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def db_path(self) -> Path:
        p = PROJECT_ROOT / self.database_path
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def log_path(self) -> Path:
        p = PROJECT_ROOT / self.log_file
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def target_url(self) -> str:
        return (
            f"{self.target_base}"
            f"?o={self.sort_column}&r=d&flimit=200&"
            "fonlycharhost=1&ftlds[]=2&fadult=1"
        )


settings = Settings()
