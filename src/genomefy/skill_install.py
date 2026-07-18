from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MANIFEST = ".genomefy-install.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_skill(source: str | Path, target: str | Path) -> dict[str, Any]:
    source_path = Path(source).resolve()
    target_path = Path(target).resolve()
    if not (source_path / "SKILL.md").is_file():
        raise FileNotFoundError(f"Invalid Genomefy skill source: {source_path}")
    backup: str | None = None
    if target_path.exists():
        manifest_path = target_path / MANIFEST
        if not manifest_path.is_file():
            raise FileExistsError(f"Refusing to overwrite unmanaged skill: {target_path}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = target_path.with_name(f"{target_path.name}.backup-{stamp}")
        shutil.copytree(target_path, backup_path)
        backup = str(backup_path)
        shutil.rmtree(target_path)
    shutil.copytree(source_path, target_path)
    files = {
        path.relative_to(target_path).as_posix(): _hash(path)
        for path in sorted(target_path.rglob("*")) if path.is_file()
    }
    project_root = source_path.parents[1]
    manifest = {
        "schema": "genomefy-skill-install-v1", "source": str(source_path), "project_root": str(project_root),
        "installed_at": datetime.now(timezone.utc).isoformat(), "files": files,
    }
    (target_path / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"installed": str(target_path), "backup": backup, "files": len(files)}
