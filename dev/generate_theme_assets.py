"""Generate the four synthetic built-in theme images for ZhiJing.

These assets are original synthetic paintings produced by this script. They are
placeholders for the four new built-in scenes described in
docs/development-plan.md and may be replaced by licensed photography later.
Run with a Python that has Pillow and numpy:

    python dev/generate_theme_assets.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "frontend" / "src" / "assets"
W, H = 2172, 724


def gradient(stops: list[tuple[float, tuple[int, int, int]]]) -> Image.Image:
    positions = [position for position, _ in stops]
    colors = np.array([color for _, color in stops], dtype=np.float32)
    t = np.linspace(0, 1, H)
    rows = np.stack([np.interp(t, positions, colors[:, channel]) for channel in range(3)], axis=1)
    return Image.fromarray(np.repeat(rows[:, None, :], W, axis=1).astype(np.uint8))


def linear_gradient(size: tuple[int, int], stops: list[tuple[float, tuple[int, int, int]]], vertical: bool = True) -> Image.Image:
    width, height = size
    length = height if vertical else width
    positions = [position for position, _ in stops]
    colors = np.array([color for _, color in stops], dtype=np.float32)
    line = np.stack([np.interp(np.linspace(0, 1, length), positions, colors[:, channel]) for channel in range(3)], axis=1)
    line = line.astype(np.uint8)
    if vertical:
        array = np.repeat(line[:, None, :], width, axis=1)
    else:
        array = np.repeat(line[None, :, :], height, axis=0)
    return Image.fromarray(array)


def radial(size: tuple[int, int], inner: tuple[int, int, int], alpha: int, center=(0.5, 0.5), radius=0.6) -> Image.Image:
    width, height = size
    ys, xs = np.mgrid[0:height, 0:width]
    cx, cy = center[0] * width, center[1] * height
    distance = np.sqrt(((xs - cx) / (radius * width)) ** 2 + ((ys - cy) / (radius * height)) ** 2)
    mask = np.clip(1 - distance, 0, 1) ** 1.6 * alpha
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[..., :3] = inner
    rgba[..., 3] = mask.astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def vignette(image: Image.Image, strength: float = 0.42) -> Image.Image:
    width, height = image.size
    ys, xs = np.mgrid[0:height, 0:width]
    nx = (xs - width / 2) / (width / 2)
    ny = (ys - height / 2) / (height / 2)
    mask = np.clip((nx ** 2 + ny ** 2 - 0.25) * strength, 0, 1)
    array = np.asarray(image).astype(np.float32)
    array *= (1 - mask[..., None])
    return Image.fromarray(array.clip(0, 255).astype(np.uint8))


def grain(image: Image.Image, strength: int = 4, seed: int = 1) -> Image.Image:
    rng = np.random.default_rng(seed)
    array = np.asarray(image).astype(np.int16)
    noise = rng.integers(-strength, strength + 1, size=array.shape[:2], dtype=np.int16)
    array = np.clip(array + noise[..., None], 0, 255).astype(np.uint8)
    return Image.fromarray(array)


def add_blurred_shapes(base: Image.Image, draw, blur: float = 9) -> Image.Image:
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw(layer)
    return Image.alpha_composite(base, layer.filter(ImageFilter.GaussianBlur(blur)))


def draw_morning() -> Image.Image:
    image = gradient([(0.0, (213, 196, 165)), (0.55, (190, 170, 136)), (0.62, (176, 154, 120)), (0.63, (104, 72, 44)), (1.0, (58, 38, 23))]).convert("RGBA")
    draw = ImageDraw.Draw(image)
    wx0, wy0, wx1, wy1 = int(0.06 * W), int(0.04 * H), int(0.68 * W), int(0.60 * H)
    view = linear_gradient((wx1 - wx0, wy1 - wy0), [(0.0, (247, 236, 213)), (0.5, (228, 230, 190)), (1.0, (168, 186, 132))])
    rng = random.Random(7)
    view_draw = ImageDraw.Draw(view, "RGBA")
    for _ in range(120):
        x, y = rng.uniform(0, wx1 - wx0), rng.uniform(0.2, 1.0) * (wy1 - wy0)
        radius = rng.uniform(8, 55)
        shade = rng.choice([(88, 106, 62, 120), (104, 124, 70, 110), (150, 163, 96, 90)])
        view_draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=shade)
    view = view.filter(ImageFilter.GaussianBlur(14)).convert("RGBA")
    sunlight = radial(view.size, (255, 241, 196), 150, center=(0.3, 0.15), radius=0.6)
    view = Image.alpha_composite(view, sunlight)
    image.paste(view, (wx0, wy0))
    # Window frame and mullions.
    frame = (88, 61, 38, 255)
    draw.rectangle([wx0 - 10, wy0 - 10, wx1 + 10, wy1 + 10], outline=frame, width=18)
    for fraction in (0.34, 0.67):
        x = wx0 + int((wx1 - wx0) * fraction)
        draw.rectangle([x - 7, wy0, x + 7, wy1], fill=frame)
    draw.rectangle([wx0, wy0 + int((wy1 - wy0) * 0.5) - 6, wx1, wy0 + int((wy1 - wy0) * 0.5) + 6], fill=frame)
    # Soft curtain falloff on the right.
    curtain = Image.new("RGBA", (int(0.11 * W), int(0.64 * H)), (0, 0, 0, 0))
    ImageDraw.Draw(curtain).rectangle([0, 0, curtain.width, curtain.height], fill=(245, 237, 218, 150))
    curtain = curtain.filter(ImageFilter.GaussianBlur(18))
    image.alpha_composite(curtain, (int(0.66 * W), int(0.02 * H)))
    # Desk surface.
    desk = linear_gradient((W, int(0.38 * H)), [(0.0, (150, 104, 62)), (0.25, (128, 85, 48)), (1.0, (62, 39, 22))])
    image.paste(desk, (0, int(0.62 * H)))
    desk_draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(18):
        y = rng.uniform(0.64, 0.99) * H
        desk_draw.line([(rng.uniform(0, 0.4) * W, y), (rng.uniform(0.55, 1.0) * W, y + rng.uniform(-6, 6))], fill=(74, 47, 26, 34), width=rng.randint(1, 2))
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse([int(0.45 * W), int(0.88 * H), int(0.86 * W), int(1.03 * H)], fill=(38, 22, 12, 120))
    sdraw.ellipse([int(0.82 * W), int(0.70 * H), int(0.95 * W), int(0.79 * H)], fill=(38, 22, 12, 110))
    sdraw.ellipse([int(0.02 * W), int(0.86 * H), int(0.17 * W), int(0.95 * H)], fill=(38, 22, 12, 110))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))
    # Open notebook with faint page lines.
    book = [(int(0.47 * W), int(0.80 * H)), (int(0.78 * W), int(0.76 * H)), (int(0.82 * W), int(0.94 * H)), (int(0.50 * W), int(0.97 * H))]
    draw.polygon(book, fill=(244, 237, 220, 255))
    spine = [(int(0.645 * W), int(0.779 * H)), (int(0.662 * W), int(0.955 * H))]
    draw.line(spine, fill=(176, 159, 130, 255), width=5)
    for side in (0, 1):
        for line in range(7):
            y_top = 0.80 + line * 0.022
            if side == 0:
                draw.line([(0.48 * W + line * 2, y_top * H + 20), (0.63 * W, y_top * H + 14)], fill=(190, 180, 160, 160), width=2)
            else:
                draw.line([(0.67 * W, y_top * H + 12), (0.80 * W, y_top * H + 4)], fill=(190, 180, 160, 160), width=2)
    # Pencil.
    draw.line([(0.84 * W, 0.92 * H), (0.94 * W, 0.86 * H)], fill=(196, 150, 54, 255), width=7)
    # Mug on a saucer.
    mug_x, mug_y = int(0.885 * W), int(0.70 * H)
    draw.ellipse([mug_x - 58, mug_y - 14, mug_x + 58, mug_y + 20], fill=(224, 214, 194, 255))
    draw.rounded_rectangle([mug_x - 40, mug_y - 76, mug_x + 40, mug_y + 4], radius=16, fill=(238, 231, 216, 255))
    draw.arc([mug_x + 30, mug_y - 60, mug_x + 74, mug_y - 16], 270, 90, fill=(238, 231, 216, 255), width=10)
    draw.ellipse([mug_x - 36, mug_y - 82, mug_x + 36, mug_y - 62], fill=(205, 190, 166, 255))
    # Plant on the left.
    pot = [(0.035 * W, 0.90 * H), (0.15 * W, 0.90 * H), (0.13 * W, 0.74 * H), (0.055 * W, 0.74 * H)]
    draw.polygon(pot, fill=(160, 118, 82, 255))
    for _ in range(9):
        angle = rng.uniform(-1.2, 0.4)
        base_x, base_y = 0.095 * W, 0.74 * H
        length = rng.uniform(70, 150)
        tip_x = base_x + math.sin(angle) * length
        tip_y = base_y - math.cos(angle) * length
        draw.line([(base_x, base_y), (tip_x, tip_y)], fill=(62, 84, 48, 255), width=rng.randint(4, 7))
        draw.ellipse([tip_x - 26, tip_y - 12, tip_x + 26, tip_y + 12], fill=rng.choice([(74, 100, 52, 255), (90, 118, 60, 255)]))
    # Sunlight shaft across the desk.
    beam = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(beam).polygon([(int(0.16 * W), 0), (int(0.42 * W), 0), (int(0.72 * W), H), (int(0.36 * W), H)], fill=(255, 237, 190, 30))
    image = Image.alpha_composite(image, beam.filter(ImageFilter.GaussianBlur(26)))
    image = image.filter(ImageFilter.GaussianBlur(0.6))
    return grain(vignette(image, 0.35), 3, 11)


def draw_seaside() -> Image.Image:
    image = linear_gradient((W, H), [(0.0, (100, 68, 43)), (0.5, (128, 88, 57)), (1.0, (74, 47, 30))]).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    # Wooden plank wall.
    for _ in range(16):
        y = random.uniform(0, H)
        draw.line([(0, y), (W, y + random.uniform(-14, 14))], fill=(70, 44, 27, 80), width=random.randint(2, 5))
    wx0, wy0, wx1, wy1 = int(0.07 * W), int(0.03 * H), int(0.87 * W), int(0.64 * H)
    view = linear_gradient((wx1 - wx0, wy1 - wy0), [
        (0.0, (176, 222, 241)), (0.34, (222, 242, 250)), (0.52, (198, 230, 240)),
        (0.54, (72, 137, 160)), (0.75, (52, 110, 132)), (1.0, (36, 82, 102)),
    ])
    view_draw = ImageDraw.Draw(view, "RGBA")
    horizon = int((wy1 - wy0) * 0.54)
    view_draw.rectangle([0, horizon, view.width, horizon + 5], fill=(238, 250, 252, 220))
    view_draw.ellipse([view.width * 0.28, horizon - 90, view.width * 0.28 + 130, horizon - 20], fill=(255, 250, 220, 120))
    view = view.filter(ImageFilter.GaussianBlur(1))
    for _ in range(40):
        y = random.uniform(horizon + 10, view.height)
        x = random.uniform(0, view.width)
        length = random.uniform(20, 90)
        view_draw.line([(x, y), (x + length, y)], fill=(255, 255, 255, random.randint(18, 60)), width=random.randint(1, 3))
    image.paste(view, (wx0, wy0))
    frame = (64, 40, 24, 255)
    draw.rectangle([wx0 - 12, wy0 - 12, wx1 + 12, wy1 + 12], outline=frame, width=24)
    for fraction in (0.33, 0.66):
        x = wx0 + int((wx1 - wx0) * fraction)
        draw.rectangle([x - 8, wy0, x + 8, wy1], fill=frame)
    # White curtains on both sides.
    curtain = Image.new("RGBA", (int(0.16 * W), int(0.70 * H)), (0, 0, 0, 0))
    cdraw = ImageDraw.Draw(curtain)
    cdraw.rectangle([0, 0, int(0.09 * W), curtain.height], fill=(250, 247, 238, 190))
    cdraw.rectangle([int(0.18 * W), 0, int(0.27 * W), curtain.height], fill=(250, 247, 238, 150))
    curtain = curtain.filter(ImageFilter.GaussianBlur(12))
    image.alpha_composite(curtain, (int(0.83 * W), int(0.0 * H)))
    curtain_left = curtain.transpose(Image.FLIP_LEFT_RIGHT)
    image.alpha_composite(curtain_left, (0, 0))
    # Desktop and objects.
    desk = linear_gradient((W, int(0.34 * H)), [(0.0, (160, 112, 70)), (1.0, (88, 57, 36))])
    image.paste(desk, (0, int(0.78 * H)))
    page = [(int(0.28 * W), int(0.815 * H)), (int(0.50 * W), int(0.795 * H)), (int(0.52 * W), int(0.905 * H)), (int(0.30 * W), int(0.93 * H))]
    draw.polygon(page, fill=(247, 240, 226, 255))
    draw.line([(int(0.395 * W), int(0.805 * H)), (int(0.405 * W), int(0.918 * H))], fill=(196, 180, 154, 255), width=4)
    for side in range(2):
        for line in range(5):
            y = (0.835 + line * 0.017) * H
            if side == 0:
                draw.line([(int(0.30 * W), y + 8), (int(0.385 * W), y + 3)], fill=(203, 191, 170, 150), width=2)
            else:
                draw.line([(int(0.415 * W), y + 3), (int(0.505 * W), y - 4)], fill=(203, 191, 170, 150), width=2)
    draw.ellipse([int(0.60 * W), int(0.795 * H), int(0.655 * W), int(0.865 * H)], fill=(250, 248, 242, 255))
    draw.ellipse([int(0.605 * W), int(0.802 * H), int(0.625 * W), int(0.825 * H)], fill=(210, 199, 181, 255))
    draw.arc([int(0.645 * W), int(0.812 * H), int(0.688 * W), int(0.852 * H)], 270, 90, fill=(250, 248, 242, 255), width=7)
    draw.polygon([(int(0.72 * W), int(0.888 * H)), (int(0.78 * W), int(0.873 * H)), (int(0.79 * W), int(0.902 * H)), (int(0.71 * W), int(0.915 * H))], fill=(214, 178, 132, 255))
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.ellipse([int(0.26 * W), int(0.87 * H), int(0.55 * W), int(0.98 * H)], fill=(40, 24, 14, 105))
    sdraw.ellipse([int(0.58 * W), int(0.85 * H), int(0.71 * W), int(0.93 * H)], fill=(40, 24, 14, 90))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    glow = radial(image.size, (255, 250, 226), 90, center=(0.46, 0.28), radius=0.55)
    image = Image.alpha_composite(image, glow)
    image = image.filter(ImageFilter.GaussianBlur(0.6))
    return grain(vignette(image, 0.38), 3, 22)


def draw_train() -> Image.Image:
    image = linear_gradient((W, H), [(0.0, (43, 34, 33)), (0.5, (61, 46, 41)), (1.0, (29, 23, 22))]).convert("RGBA")
    draw = ImageDraw.Draw(image, "RGBA")
    wx0, wy0, wx1, wy1 = int(0.10 * W), int(0.04 * H), int(0.90 * W), int(0.63 * H)
    view = linear_gradient((wx1 - wx0, wy1 - wy0), [
        (0.0, (43, 38, 78)), (0.28, (105, 58, 92)), (0.52, (201, 104, 82)),
        (0.66, (243, 158, 92)), (0.70, (250, 196, 128)), (1.0, (88, 66, 54)),
    ])
    vdraw = ImageDraw.Draw(view, "RGBA")
    # Sun and hills.
    vdraw.ellipse([view.width * 0.58, view.height * 0.36, view.width * 0.58 + 130, view.height * 0.36 + 130], fill=(255, 224, 158, 235))
    vdraw.polygon([(0, view.height * 0.63), (view.width * 0.2, view.height * 0.50), (view.width * 0.42, view.height * 0.63)], fill=(53, 40, 48, 255))
    vdraw.polygon([(view.width * 0.34, view.height * 0.63), (view.width * 0.6, view.height * 0.47), (view.width * 0.86, view.height * 0.63)], fill=(44, 34, 42, 255))
    vdraw.rectangle([0, view.height * 0.62, view.width, view.height], fill=(39, 31, 30, 255))
    for _ in range(12):
        x = random.uniform(0, view.width)
        vdraw.line([(x, view.height * 0.60), (x, view.height * 0.30)], fill=(22, 18, 20, 140), width=2)
    for _ in range(5):
        x = random.uniform(0, view.width)
        vdraw.line([(x, 0), (x, view.height * 0.6)], fill=(20, 16, 18, 90), width=1)
    image.paste(view, (wx0, wy0))
    frame = (32, 24, 22, 255)
    draw.rounded_rectangle([wx0 - 18, wy0 - 18, wx1 + 18, wy1 + 18], radius=42, outline=frame, width=26)
    draw.rounded_rectangle([wx0 - 3, wy0 - 3, wx1 + 3, wy1 + 3], radius=28, outline=(120, 92, 74, 160), width=3)
    # Interior reflections.
    reflection = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(reflection).polygon([(int(0.23 * W), wy0), (int(0.31 * W), wy0), (int(0.18 * W), wy1), (int(0.10 * W), wy1)], fill=(255, 236, 205, 26))
    image = Image.alpha_composite(image, reflection.filter(ImageFilter.GaussianBlur(18)))
    # Seat in the foreground.
    draw.rounded_rectangle([int(-0.04 * W), int(0.66 * H), int(0.36 * W), int(0.98 * H)], radius=60, fill=(101, 68, 56, 255))
    draw.arc([int(-0.02 * W), int(0.63 * H), int(0.31 * W), int(0.94 * H)], 205, 335, fill=(158, 109, 80, 200), width=10)
    draw.arc([int(-0.03 * W), int(0.67 * H), int(0.35 * W), int(1.02 * H)], 200, 340, fill=(64, 42, 34, 200), width=4)
    for _ in range(5):
        y = random.uniform(0.74, 0.95) * H
        draw.line([(int(0.02 * W), y), (int(0.30 * W), y + random.uniform(-8, 8))], fill=(58, 38, 32, 140), width=2)
    # Tray and lamp on the right.
    draw.rounded_rectangle([int(0.62 * W), int(0.82 * H), int(0.97 * W), int(0.90 * H)], radius=14, fill=(63, 45, 36, 255))
    lamp = radial(image.size, (255, 214, 144), 120, center=(0.80, 0.72), radius=0.20)
    image = Image.alpha_composite(image, lamp)
    draw.rounded_rectangle([int(0.79 * W), int(0.70 * H), int(0.83 * W), int(0.80 * H)], radius=8, fill=(209, 158, 92, 255))
    draw.ellipse([int(0.77 * W), int(0.68 * H), int(0.85 * W), int(0.73 * H)], fill=(240, 196, 124, 255))
    image = image.filter(ImageFilter.GaussianBlur(0.5))
    return grain(vignette(image, 0.4), 3, 33)


def draw_pixel() -> Image.Image:
    low_w, low_h = 181, 60
    image = Image.new("RGB", (low_w, low_h))
    pixels = image.load()
    sky = [(9, 18, 41), (15, 32, 63), (24, 51, 82), (34, 70, 98)]
    for y in range(low_h):
        t = y / (low_h - 1)
        index = min(3, int(t * 4))
        next_index = min(3, index + 1)
        blend = t * 4 - index
        color = tuple(round(sky[index][channel] * (1 - blend) + sky[next_index][channel] * blend) for channel in range(3))
        for x in range(low_w):
            pixels[x, y] = color
    draw = ImageDraw.Draw(image)
    rng = random.Random(2026)
    for _ in range(70):
        x, y = rng.randrange(low_w), rng.randrange(0, 30)
        draw.point((x, y), fill=rng.choice([(255, 255, 230), (206, 232, 255), (255, 240, 180)]))
    # Moon.
    draw.ellipse([126, 6, 138, 18], fill=(255, 232, 158))
    draw.ellipse([129, 8, 133, 12], fill=(232, 205, 138))
    # Shooting star.
    for step in range(7):
        draw.point((40 + step, 22 - step), fill=(255, 255, 255))
    # Hills and field.
    draw.polygon([(0, 40), (28, 31), (58, 39), (92, 29), (128, 38), (161, 31), (181, 38), (181, 60), (0, 60)], fill=(12, 38, 33))
    draw.rectangle([0, 43, low_w, low_h], fill=(15, 49, 39))
    for y in range(44, low_h, 3):
        draw.line([(0, y), (low_w, y)], fill=(18, 56, 44))
    # Cabin with a lit window.
    draw.rectangle([132, 38, 149, 47], fill=(31, 44, 42))
    draw.polygon([(129, 38), (140, 32), (152, 38)], fill=(42, 52, 46))
    draw.rectangle([138, 41, 143, 45], fill=(255, 206, 112))
    # Tree silhouette.
    draw.rectangle([34, 34, 37, 49], fill=(9, 28, 26))
    draw.polygon([(24, 42), (36, 26), (48, 42)], fill=(11, 33, 30))
    draw.polygon([(26, 36), (36, 22), (46, 36)], fill=(13, 38, 34))
    # Fireflies.
    for _ in range(18):
        x, y = rng.randrange(0, low_w), rng.randrange(40, 58)
        draw.point((x, y), fill=rng.choice([(255, 226, 126), (214, 255, 160)]))
    return image.resize((W, H), Image.Resampling.NEAREST)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    scenes = {
        "morning": draw_morning,
        "seaside": draw_seaside,
        "train": draw_train,
        "pixel": draw_pixel,
    }
    for name, builder in scenes.items():
        image = builder()
        target = ASSETS / f"{name}.jpg"
        image.convert("RGB").save(target, "JPEG", quality=88, optimize=True, progressive=True)
        print(f"wrote {target.relative_to(ROOT)} ({image.width}x{image.height})")


if __name__ == "__main__":
    main()
