from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


BASELINE = "0.7.1"
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
    return source[match.start():end]


def method_blocks(source: str) -> dict[str, str]:
    matches = list(
        re.finditer(r"^    (?:async )?def ([A-Za-z0-9_]+)\s*\(", source, re.M)
    )
    result: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.start()
        # Include contiguous decorators immediately above the method.
        while start > 0:
            prev_end = start - 1
            prev_start = source.rfind("\n", 0, prev_end) + 1
            line = source[prev_start:prev_end].strip()
            if line.startswith("@"):
                start = prev_start
                continue
            break
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        result[match.group(1)] = source[start:end].rstrip()
    return result


def js_class(source: str, name: str) -> str:
    marker = f"class {name}"
    start = source.find(marker)
    if start < 0:
        raise RuntimeError(f"Classe JS introuvable: {name}")
    candidates = [
        pos
        for pos in (
            source.find("\nclass ", start + len(marker)),
            source.find("\ncustomElements.define", start + len(marker)),
        )
        if pos > start
    ]
    end = min(candidates) if candidates else len(source)
    return source[start:end].rstrip()


def fail(message: str) -> None:
    print(f"PROTECTED ENGINE CHANGED: {message}", file=sys.stderr)
    raise SystemExit(1)


# Protect every method that existed in the v0.7.1 JustWatch engine. New Local
# methods/classes are allowed, but an existing historical method must stay
# byte-for-byte identical.
sources_path = "custom_components/streaming_top_fr/sources.py"
old_class = class_block(baseline(sources_path), "JustWatchClient")
new_class = class_block(current(sources_path), "JustWatchClient")
old_methods = method_blocks(old_class)
new_methods = method_blocks(new_class)
for name, old in old_methods.items():
    new = new_methods.get(name)
    if new is None:
        fail(f"JustWatchClient.{name} supprimée")
    if new != old:
        fail(f"JustWatchClient.{name} diffère de {BASELINE}")


# Protect the coordinator paths that build the historical Streaming cards.
coord_path = "custom_components/streaming_top_fr/coordinator.py"
old_coord = method_blocks(class_block(baseline(coord_path), "StreamingTopCoordinator"))
new_coord = method_blocks(class_block(current(coord_path), "StreamingTopCoordinator"))
for name in ("_build_netflix", "_async_update_data"):
    if new_coord.get(name) != old_coord.get(name):
        fail(f"StreamingTopCoordinator.{name} diffère de {BASELINE}")


# Protect the two historical Lovelace cards exactly. Streaming Local lives in
# a separate class and can evolve independently.
js_path = "custom_components/streaming_top_fr/www/streaming-top-fr-card.js"
old_js = baseline(js_path)
new_js = current(js_path)
for name in ("StreamingTopFrCard", "StreamingTopFrCatalogCard"):
    if js_class(new_js, name) != js_class(old_js, name):
        fail(f"classe JS {name} diffère de {BASELINE}")


print("Historical Streaming/Top engine matches v0.7.1.")
