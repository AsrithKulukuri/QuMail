import os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DEMO_EMAIL_MODE']='true'
os.environ['SECRET_KEY']='test-secret'
