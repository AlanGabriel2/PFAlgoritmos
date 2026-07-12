"""Genera hojas pixel-perfect con celdas divisibles y anclaje inferior común.

Los originales nunca se sobrescriben. Cada personaje conserva una escala uniforme
entre acciones; los fotogramas se centran horizontalmente y se apoyan en la misma
línea de suelo.
"""

from pathlib import Path
from statistics import median

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]

SHEETS = {
    "player": ("assets/images/player/player_sheet.png", 3, 4, (128, 128), 96),
    "player_idle": (
        "assets/images/player/generated/player_idle_v2_alpha_master.png",
        2, 4, (160, 144), 112,
    ),
    "player_walk": (
        "assets/images/player/generated/player_walk_v3_alpha_master.png",
        2, 4, (160, 144), 112,
    ),
    "player_attack": (
        "assets/images/player/generated/player_attack_v2_alpha_master.png",
        2, 4, (160, 144), 112,
    ),
    "bug": ("assets/images/enemies/bug_sheet.png", 3, 6, (96, 96), 54),
    "spaghetti": ("assets/images/enemies/spaghetti_sheet.png", 3, 4, (160, 112), 72),
    "leak": ("assets/images/enemies/leak_sheet.png", 3, 4, (144, 112), 48),
    "deadline": ("assets/images/enemies/deadline_sheet.png", 3, 4, (144, 128), 96),
    "deadline_idle": (
        "assets/images/enemies/generated/deadline_idle_v2_alpha_master.png",
        2, 4, (176, 160), 128,
    ),
    "deadline_walk": (
        "assets/images/enemies/generated/deadline_walk_v2_alpha_master.png",
        2, 4, (176, 160), 128,
    ),
    "deadline_attack": (
        "assets/images/enemies/generated/deadline_attack_v2_alpha_master.png",
        2, 4, (176, 160), 128,
    ),
    "miniboss": ("assets/images/enemies/miniboss_sheet.png", 3, 4, (320, 256), 192),
    "boss": ("assets/images/enemies/boss_sheet.png", 4, 8, (352, 352), 288),
    "miniboss_attack": (
        "assets/images/enemies/generated/miniboss_attack_v2_alpha_master.png",
        2, 4, (256, 256), 220,
    ),
    "miniboss_walk": (
        "assets/images/enemies/generated/miniboss_walk_v2_alpha_master.png",
        2, 4, (256, 256), 220,
    ),
}

def alpha_bbox(image):
    return image.getchannel("A").getbbox()


def normalize(name, source_rel, rows, cols, cell_size, reference_height):
    source = Image.open(ROOT / source_rel).convert("RGBA")
    source_w, source_h = source.size
    frame_w, frame_h = source_w // cols, source_h // rows

    frames = []
    idle_heights = []
    for row in range(rows):
        current_row = []
        for col in range(cols):
            frame = source.crop((col * frame_w, row * frame_h, (col + 1) * frame_w, (row + 1) * frame_h))
            bbox = alpha_bbox(frame)
            cropped = frame.crop(bbox) if bbox else Image.new("RGBA", (1, 1))
            current_row.append(cropped)
            if row == 0 and bbox:
                idle_heights.append(cropped.height)
        frames.append(current_row)

    idle_height = median(idle_heights) if idle_heights else 1
    scale = reference_height / idle_height
    max_w = max(frame.width * scale for row in frames for frame in row)
    max_h = max(frame.height * scale for row in frames for frame in row)
    cell_w, cell_h = cell_size
    if max_w > cell_w or max_h > cell_h:
        scale *= min(cell_w / max_w, cell_h / max_h)

    sheet = Image.new("RGBA", (cell_w * cols, cell_h * rows))
    for row, images in enumerate(frames):
        for col, frame in enumerate(images):
            new_size = (
                max(1, round(frame.width * scale)),
                max(1, round(frame.height * scale)),
            )
            scaled = frame.resize(new_size, Image.Resampling.NEAREST)
            x = col * cell_w + (cell_w - scaled.width) // 2
            y = row * cell_h + cell_h - scaled.height
            sheet.alpha_composite(scaled, (x, y))

    source_path = Path(source_rel)
    output = ROOT / source_path.with_name(f"{source_path.stem}_normalized.png")
    sheet.save(output, optimize=True)
    print(f"{name}: {output.relative_to(ROOT)} {sheet.size} ({rows}x{cols}, cell={cell_size})")


def main():
    for name, config in SHEETS.items():
        normalize(name, *config)


if __name__ == "__main__":
    main()
