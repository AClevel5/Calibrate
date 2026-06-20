"""Regenerate the app's PWA icons from the master logo.

Run from the repository root:

    .venv/bin/python brand/generate_icons.py

Reads brand/Calibrate.png (the master, rounded-corner artwork on black) and writes
the served icons into app/static/icons/. The black corners are composited onto the
icon's own background green so iOS/Android can apply their own masking cleanly; the
maskable variant gets a safe-zone margin so the circle/squircle crop never clips.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "brand" / "Calibrate.png"
OUT = ROOT / "app" / "static" / "icons"


def build() -> None:
    orig = Image.open(SOURCE).convert("RGB")
    s = orig.size[0]
    # Sample the dark-green background from the top-center gap (above the ring).
    bg = orig.getpixel((s // 2, int(s * 0.10)))

    # Composite the rounded artwork onto a full green square (drops black corners).
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.205), fill=255)
    filled = Image.new("RGB", (s, s), bg)
    filled.paste(orig, (0, 0), mask)

    def resized(img: Image.Image, size: int) -> Image.Image:
        return img.resize((size, size), Image.LANCZOS)

    OUT.mkdir(parents=True, exist_ok=True)
    resized(filled, 192).save(OUT / "icon-192.png")
    resized(filled, 512).save(OUT / "icon-512.png")

    # Maskable: ~16% inset so the OS crop never clips the targeting ring.
    canvas = Image.new("RGB", (s, s), bg)
    inner = int(s * 0.84)
    off = (s - inner) // 2
    canvas.paste(resized(filled, inner), (off, off))
    resized(canvas, 512).save(OUT / "icon-maskable.png")

    print(f"Wrote icon-192/512/maskable to {OUT.relative_to(ROOT)} (bg {bg})")


if __name__ == "__main__":
    build()
