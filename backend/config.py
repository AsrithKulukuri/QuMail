from pathlib import Path
import json, os
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')
DB_PATH = ROOT / 'qumail.db'
SECRET_KEY = os.getenv('SECRET_KEY', 'qumail-dev-secret-change-me')
KME_ID = os.getenv('KME_ID', 'SIM-KME-001')
DEMO_EMAIL_MODE = os.getenv('DEMO_EMAIL_MODE', 'true').lower() in {'1','true','yes','on'}
SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))
IMAP_HOST = os.getenv('IMAP_HOST', 'imap.gmail.com')
IMAP_PORT = int(os.getenv('IMAP_PORT', '993'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASS = os.getenv('SMTP_PASS', '')
IMAP_USER = os.getenv('IMAP_USER', SMTP_USER)
IMAP_PASS = os.getenv('IMAP_PASS', SMTP_PASS)

# Optional two-account demo mapping. Keys are QuMail IDs; values are real mailbox credentials.
try:
    MAILBOXES = json.loads(os.getenv('MAILBOXES_JSON', '{}'))
except json.JSONDecodeError:
    MAILBOXES = {}
