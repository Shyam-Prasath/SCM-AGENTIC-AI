"""Common helpers for HexaShop SCM agents."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)


def data_path(filename: str) -> Path:
    """Return a path inside the data folder and fail clearly if missing."""
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required data file missing: {path}")
    return path


def get_llm(temperature: float = 0.2):
    """Create CrewAI Azure LLM from .env."""
    from crewai import LLM

    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    api_key = os.getenv("AZURE_OPENAI_KEY")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    if not deployment or not api_key or not endpoint:
        raise EnvironmentError(
            "Azure OpenAI settings are missing. Fill AZURE_OPENAI_DEPLOYMENT, "
            "AZURE_OPENAI_KEY, and AZURE_OPENAI_ENDPOINT in .env."
        )

    return LLM(
        model=f"azure/{deployment}",
        api_key=api_key,
        api_base=endpoint,
        api_version=api_version,
        temperature=temperature,
    )


def safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def safe_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default
