"""Small helpers for writing JSON/Markdown artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def model_to_dict(obj: Any) -> Dict:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj)


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
