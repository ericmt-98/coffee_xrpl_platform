"""Backend configuration loaded from environment / .env file."""

import os
from dotenv import load_dotenv

load_dotenv()

XUMM_APIKEY:   str = os.environ["XUMM_APIKEY"]
XUMM_APISECRET: str = os.environ["XUMM_APISECRET"]
DATABASE_URL:  str = os.environ.get("DATABASE_URL", "sqlite:///./backend.db")
