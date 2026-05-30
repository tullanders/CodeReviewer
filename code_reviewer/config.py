"""Configuration module for code-reviewer.

Loads environment variables from .env file using python-dotenv.
Exposes configuration as module-level constants.
"""

import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")
GOOGLE_SERVICE_ACCOUNT_JSON: str | None = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
MS_TENANT_ID: str | None = os.getenv("MS_TENANT_ID")
MS_CLIENT_ID: str | None = os.getenv("MS_CLIENT_ID")
MS_CLIENT_SECRET: str | None = os.getenv("MS_CLIENT_SECRET")
