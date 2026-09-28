import sys
from pathlib import Path

# Ensure api-gateway has precedence for its own 'app' module
_SERVICE_ROOT = str(Path(__file__).resolve().parent)
if _SERVICE_ROOT not in sys.path or sys.path[0] != _SERVICE_ROOT:
    if _SERVICE_ROOT in sys.path:
        sys.path.remove(_SERVICE_ROOT)
    sys.path.insert(0, _SERVICE_ROOT)
