import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / '.env')

STATE = Path(os.getenv('PACT_STATE_DIR', str(ROOT / '.local'))).resolve()
STATE.mkdir(parents=True, exist_ok=True)
DATA = Path(os.getenv('PACT_SOURCE_DIR', str(ROOT.parent / 'PACT-Compute-data-preflight'))).resolve()
DATABASE = os.getenv('PACT_DATABASE_URL', f'sqlite:///{(STATE / "pact.db").as_posix()}')
if DATABASE.startswith(('postgres://', 'postgresql://')):
    DATABASE = 'postgresql+pg8000://' + DATABASE.split('://', 1)[1]
DB_TLS = os.getenv('PACT_DB_TLS', '0') == '1'

URL = os.getenv('PACT_URL', 'http://127.0.0.1:8765').rstrip('/')
COOKIE_SECURE = os.getenv('PACT_SECURE_COOKIE', '0') == '1'
FRONTEND = ROOT / 'frontend' / 'dist'
GROQ_KEY = os.getenv('GROQ_API_KEY')
LLM_KEY = GROQ_KEY or os.getenv('PACT_LLM_API_KEY')
LLM_URL = ('https://api.groq.com/openai/v1' if GROQ_KEY else os.getenv('PACT_LLM_BASE_URL', 'https://api.openai.com/v1')).rstrip('/')
LLM_MODEL = os.getenv('GROQ_MODEL', 'openai/gpt-oss-20b') if GROQ_KEY else os.getenv('PACT_LLM_MODEL')
LLM_PROVIDER = 'Groq' if GROQ_KEY else 'Configured provider'
GPU_ZONE = os.getenv('PACT_RUNNER_GRID_ZONE', '').strip().upper() or None
SESSION_SECONDS = 8 * 3600
