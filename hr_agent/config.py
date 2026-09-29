import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
DATA = ROOT / 'data'
RUNTIME = Path(os.getenv('HR_RUNTIME', str(ROOT / '.runtime')))
RUNTIME.mkdir(parents=True, exist_ok=True)

def live():
    return os.getenv('HR_MODE', 'demo') == 'live'

def model():
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini-2025-04-14'), timeout=60, max_retries=2)
