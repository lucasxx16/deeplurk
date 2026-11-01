"""The copied historical entry point must not dispatch live tasks."""
import subprocess
import sys
from pathlib import Path

p = Path(__file__).resolve().parent
result = subprocess.run([sys.executable, str(p / 'historical_supervisor.py'), '--config', str(p / 'README.md')], capture_output=True, text=True, encoding='utf-8')
assert result.returncode != 0
assert 'live dispatch disabled' in result.stderr
print('PASS: historical live entry point disabled')
