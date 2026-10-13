"""
@file: dependencies.py
@author: Samuel Stolarik
@description:
    Platform dependency
    declaration file
    (e.g. database,
    connection or environment
    file
"""
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict



class Settings(BaseSettings):
    data_dir: Path = Path("./data")

    model_config=SettingsConfigDict(env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()

