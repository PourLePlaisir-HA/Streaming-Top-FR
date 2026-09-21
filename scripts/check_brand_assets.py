from __future__ import annotations

from pathlib import Path
import struct


ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "custom_components" / "streaming_top_fr" / "brand"


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AssertionError(f"{path.name} is not a valid PNG")
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise AssertionError(f"{path.name} has no valid PNG IHDR")
    return struct.unpack(">II", data[16:24])


icon = BRAND / "icon.png"
logo = BRAND / "logo.png"

assert icon.is_file(), "brand/icon.png is missing"
assert logo.is_file(), "brand/logo.png is missing"

icon_width, icon_height = png_size(icon)
logo_width, logo_height = png_size(logo)

assert icon_width == icon_height, (
    f"brand/icon.png must be square, got {icon_width}x{icon_height}"
)
assert icon_width >= 128, (
    f"brand/icon.png is too small: {icon_width}x{icon_height}"
)
assert logo_width >= 128 and logo_height >= 128, (
    f"brand/logo.png is unexpectedly small: {logo_width}x{logo_height}"
)

print(
    "Brand assets OK: "
    f"icon={icon_width}x{icon_height}, logo={logo_width}x{logo_height}"
)
