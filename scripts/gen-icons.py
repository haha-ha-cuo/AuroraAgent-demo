"""生成占位图标（纯色 RGBA PNG，纯 stdlib）。正式开发时替换为真实图标后删除本脚本。

注意：Tauri 的 tauri-build 要求图标为 RGBA（color type 6），RGB 会报
``icon ... is not RGBA``。
"""

import struct
import zlib
from pathlib import Path


def write_png(path: Path, size: int, rgba: tuple[int, int, int, int]) -> None:
    w = h = size
    raw = b"".join(b"\x00" + bytes(rgba) * w for _ in range(h))

    def chunk(typ: bytes, data: bytes) -> bytes:
        body = typ + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)  # 8-bit RGBA
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    icons = root / "apps" / "desktop" / "src-tauri" / "icons"
    color = (99, 102, 241, 255)  # indigo + 不透明
    for size, name in [(32, "32x32.png"), (128, "128x128.png"), (512, "icon.png")]:
        write_png(icons / name, size, color)
        print(f"生成 {icons / name}")


if __name__ == "__main__":
    main()
