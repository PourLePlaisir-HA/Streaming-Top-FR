from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


BASELINE = "1272a4a878d425f33591f7a69428759d0057ce88"
ROOT = Path(__file__).resolve().parents[1]


def current(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def baseline(path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{BASELINE}:{path}"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )


def class_block(source: str, name: str) -> str:
    match = re.search(rf"^class {re.escape(name)}\b", source, re.M)
    if not match:
        raise RuntimeError(f"Classe introuvable: {name}")
    next_match = re.search(r"^class [A-Za-z0-9_]+\b", source[match.end():], re.M)
    end = match.end() + next_match.start() if next_match else len(source)
    return source[match.start():end].rstrip()


def fail(message: str) -> None:
    print(f"PROTECTED LOCAL ENGINE CHANGED: {message}", file=sys.stderr)
    raise SystemExit(1)


local_path = "custom_components/streaming_top_fr/local_library.py"
if current(local_path) != baseline(local_path):
    fail("local_library.py diffère de la stable 0.8.1")

sources_path = "custom_components/streaming_top_fr/sources.py"
old_local = class_block(baseline(sources_path), "LocalMetadataClient")
new_local = class_block(current(sources_path), "LocalMetadataClient")
if new_local != old_local:
    fail("LocalMetadataClient diffère de la stable 0.8.1")

print("Streaming Local parser/metadata engine matches stable 0.8.1.")
