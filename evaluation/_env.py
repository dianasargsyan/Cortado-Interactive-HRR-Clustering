"""
Paths shared by the evaluation package and the experiments, imported first by every experiment:

    from evaluation._env import ROOT, CACHE, require_cortado_env
    require_cortado_env()

``require_cortado_env`` stops an experiment when the installed packages are not the versions in
``requirements-evaluation.txt``: other versions run as well, but can give other numbers.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache" / "variants"
DATA = ROOT / "data"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PINNED = {"numpy": "1.26.4", "scipy": "1.15.3", "pandas": "2.3.3", "pm4py": "2.4.1",
          "cortado-core": "1.3.27"}


def require_cortado_env(strict: bool = True) -> None:
    """Stop (with strict=False: warn) unless the pinned package versions are installed."""
    wrong = []
    for name, want in PINNED.items():
        try:
            have = metadata.version(name)
        except metadata.PackageNotFoundError:
            have = "not installed"
        if have != want:
            wrong.append(f"{name} {have} instead of {want}")
    if not wrong:
        return
    msg = ("\n  Package versions differ from requirements-evaluation.txt: " + "; ".join(wrong) +
           "\n  Install them with: pip install -r requirements-evaluation.txt\n")
    if strict:
        raise SystemExit(msg)
    print(msg, file=sys.stderr)
