import os
from PIL import Image
import math

def remove_magenta(img_path):
    try:
        img = Image.open(img_path).convert("RGBA")
        data = img.getdata()
        new_data = []
        for item in data:
            r, g, b, a = item
            # Calculate distance to pure magenta (255, 0, 255)
            dist = math.sqrt((r - 255)**2 + (g - 0)**2 + (b - 255)**2)
            if dist < 120:  # aggressive threshold to catch anti-aliasing
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append(item)
        img.putdata(new_data)
        img.save(img_path)
        print(f"Processed {img_path}")
    except Exception as e:
        print(f"Failed to process {img_path}: {e}")

assets = ["assets/player.png", "assets/enemy.png", "assets/miniboss.png", "assets/boss.png"]
for asset in assets:
    remove_magenta(asset)
