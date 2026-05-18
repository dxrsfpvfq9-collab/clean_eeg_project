"""Shared pytest fixtures and path setup.

`pythonpath = .` in pytest.ini already puts the project root on sys.path,
but we add it again here as a belt-and-braces measure for IDEs that run
pytest with a different cwd.
"""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
