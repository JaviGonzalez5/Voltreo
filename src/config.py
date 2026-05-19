"""
Configuración central de la aplicación.
Lee variables de entorno desde .env y expone valores por defecto editables.
"""
from __future__ import annotations

import os
from pathlib import Path
from datetime import time

from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from pydantic import Field

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class AppSettings(BaseSettings):
    # --- Syltek ---
    syltek_url: str = Field(default="", env="SYLTEK_URL")
    syltek_user: str = Field(default="", env="SYLTEK_USER")
    syltek_password: str = Field(default="", env="SYLTEK_PASSWORD")

    # --- Seguridad ---
    dry_run: bool = Field(default=True, env="DRY_RUN")
    debug_mode: bool = Field(default=False, env="DEBUG_MODE")

    # --- Rutas ---
    screenshots_dir: Path = Field(
        default=BASE_DIR / "debug" / "screenshots", env="SCREENSHOTS_DIR"
    )
    html_dump_dir: Path = Field(
        default=BASE_DIR / "debug" / "html", env="HTML_DUMP_DIR"
    )
    exports_dir: Path = Field(default=BASE_DIR / "exports")
    sample_data_dir: Path = Field(default=BASE_DIR / "sample_data")

    # --- Reglas de ranking por defecto ---
    match_duration_minutes: int = 90
    courts_available: int = 4
    day_start_time: time = time(16, 0)
    day_end_time: time = time(22, 30)
    max_matches_per_week: int = 2

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def ensure_dirs(self) -> None:
        for d in [self.screenshots_dir, self.html_dump_dir, self.exports_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)


settings = AppSettings()
settings.ensure_dirs()
