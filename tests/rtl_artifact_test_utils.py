"""Fixture writers for artifacts nested beneath a case directory."""
from pathlib import Path


def write_artifact_text(path, text, *args, **kwargs):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.write_text(text, *args, **kwargs)
