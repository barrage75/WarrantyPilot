from __future__ import annotations

import sys
from pathlib import Path

DATA_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = DATA_ROOT.parent / "backend"

for import_root in (BACKEND_ROOT, DATA_ROOT):
    import_root_string = str(import_root)
    if import_root_string not in sys.path:
        sys.path.insert(0, import_root_string)
