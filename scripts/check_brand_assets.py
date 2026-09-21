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
icon_2x = BRAND / "icon@2x.png"
logo = BRAND / "logo.png"

assert icon.is_file(), "brand/icon.png is missing"
assert icon_2x.is_file(), "brand/icon@2x.png is missing"
assert logo.is_file(), "brand/logo.png is missing"

icon_width, icon_height = png_size(icon)
icon_2x_width, icon_2x_height = png_size(icon_2x)
logo_width, logo_height = png_size(logo)

assert (icon_width, icon_height) == (256, 256), (
    f"brand/icon.png must be 256x256, got {icon_width}x{icon_height}"
)
assert (icon_2x_width, icon_2x_height) == (512, 512), (
    f"brand/icon@2x.png must be 512x512, got {icon_2x_width}x{icon_2x_height}"
)
assert 128 <= min(logo_width, logo_height) <= 256, (
    f"brand/logo.png shortest side must be 128..256 px, got {logo_width}x{logo_height}"
)

print(
    "Brand assets OK: "
    f"icon={icon_width}x{icon_height}, "
    f"icon@2x={icon_2x_width}x{icon_2x_height}, "
    f"logo={logo_width}x{logo_height}"
)
