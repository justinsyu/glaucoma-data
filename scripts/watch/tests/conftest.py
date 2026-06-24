import os
import sys
from pathlib import Path

# Make ``glaucoma_watch`` importable without an editable install (the install is
# present in our normal environment, but explicit paths keep CI/test runs
# decoupled from install state).
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Tests must not hit live hosts or load real robots.txt files.
os.environ.setdefault("RETINA_WATCH_DISABLE_ROBOTS", "1")
os.environ.setdefault("RETINA_WATCH_MIN_INTERVAL_SECONDS", "0")
