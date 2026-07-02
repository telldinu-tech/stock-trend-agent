"""One-off script: generates PWA icon PNGs for the Streamlit app."""

from PIL import Image, ImageDraw, ImageFont


def make_icon(size: int, path: str):
    img = Image.new("RGB", (size, size), "#0e1117")
    draw = ImageDraw.Draw(img)
    margin = size * 0.08
    draw.rounded_rectangle([margin, margin, size - margin, size - margin],
                            radius=size * 0.18, fill="#0e1117", outline="#31333f", width=max(1, size // 64))

    pts = [
        (size * 0.20, size * 0.62),
        (size * 0.36, size * 0.48),
        (size * 0.50, size * 0.58),
        (size * 0.68, size * 0.32),
        (size * 0.82, size * 0.40),
    ]
    draw.line(pts, fill="#00c853", width=max(2, size // 24), joint="curve")
    for p in pts[-1:]:
        r = size * 0.03
        draw.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill="#00c853")

    img.save(path)


if __name__ == "__main__":
    make_icon(192, "static/icon-192.png")
    make_icon(512, "static/icon-512.png")
    print("Icons written to static/")
