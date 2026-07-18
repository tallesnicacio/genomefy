from __future__ import annotations

import json
import sys
from pathlib import Path


def project_root() -> Path:
    skill_dir = Path(__file__).resolve().parents[1]
    manifest = skill_dir / ".genomefy-install.json"
    if manifest.is_file():
        return Path(json.loads(manifest.read_text(encoding="utf-8"))["project_root"])
    return skill_dir.parents[1]


root = project_root()
source = root / "src"
if not (source / "genomefy" / "cli.py").is_file():
    raise SystemExit("Genomefy canonical package not found; reinstall the skill from its repository.")
sys.path.insert(0, str(source))

from genomefy.cli import main

raise SystemExit(main())
