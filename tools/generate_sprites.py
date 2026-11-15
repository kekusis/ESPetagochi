"""
Generate RGB565 C header arrays from food images and sponge image for ESP32 Tamagotchi.
Converts PNG/JPG images to 16x16 pixel art treats and 20x14 sponge sprite.
"""
import os
from PIL import Image
from collections import deque

UPLOAD_DIR = r"C:\Users\pezda\.gemini\antigravity\brain\8155fed1-7058-4969-ae78-4bfdb4de59ab\.user_uploaded"
HEADER_PATH = r"C:\Users\pezda\Desktop\ESPetagochi-main\firmware\include\treat_sprites.h"

FUR_COLOR = (155, 155, 155)
FUR_RGB565 = 0x9CD3

FOOD_IMAGES = [
    ("media_1794706515777_f975436c.jpg", "watermelon"),
    ("media_1794706515811_c796d47b.png", "apple"),
    ("media_1794706515842_eaaeda38.png", "pizza"),
    ("media_1794706515844_09fc6205.png", "burger"),
    ("media_1794706515863_f86d52ab.png", "mushroom"),
    ("media_1794706515880_25ca9cd9.png", "steak"),
    ("media_1794706515892_33c4bdc2.png", "fries"),
    ("media_1794706515900_2a757d0c.png", "orange"),
    ("media_1794706515908_f8587eb7.png", "sushi"),
    ("media_1794706515913_0446ac07.png", "donut"),
    ("media_1794706515917_bdb018b4.png", "salmon"),
    ("media_1794706515923_584ed5b8.png", "tomato"),
    ("media_1794706516817_95f57188.png", "lasagna"),
    ("media_1794706516825_1bf114d0.png", "cotton_candy"),
]

SPONGE_IMAGE = ("media_1794706699446_95b57b7b.png", "sponge")

TREAT_W, TREAT_H = 16, 16
SPONGE_W, SPONGE_H = 20, 14

def rgb_to_rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def flood_fill_bg(img, fur_color):
    """Flood-fill from edges to replace background with fur color."""
    w, h = img.size
    pixels = img.load()
    visited = set()
    queue = deque()
    
    # Seed from all border pixels
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))
    
    while queue:
        x, y = queue.popleft()
        if (x, y) in visited:
            continue
        visited.add((x, y))
        r, g, b, a = pixels[x, y]
        
        # Background detection: white-ish, black-ish, or transparent
        is_white = (r > 220 and g > 220 and b > 220)
        is_black = (r < 30 and g < 30 and b < 30)
        is_trans = (a < 128)
        is_near_white = (r > 200 and g > 200 and b > 200 and a > 128)
        
        if is_white or is_black or is_trans or is_near_white:
            pixels[x, y] = (*fur_color, 255)
            for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                    queue.append((nx, ny))
    
    # Also replace any remaining transparent pixels
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if a < 128:
                pixels[x, y] = (*fur_color, 255)
    
    return img

def process_image(filepath, target_w, target_h, name):
    """Load image, remove background, resize to pixel art, return RGB565 array."""
    img = Image.open(filepath).convert('RGBA')
    
    # Flood-fill background from edges
    img = flood_fill_bg(img, FUR_COLOR)
    
    # Resize to target with LANCZOS for quality
    img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    # Convert to RGB
    rgb = img.convert('RGB')
    pixels = rgb.load()
    
    result = []
    for y in range(target_h):
        for x in range(target_w):
            r, g, b = pixels[x, y]
            result.append(rgb_to_rgb565(r, g, b))
    
    print(f"  Processed {name}: {target_w}x{target_h} = {len(result)} pixels")
    return result

def main():
    print("=== Generating Treat & Sponge Sprites ===\n")
    
    sprites = []
    
    # Process food images
    print("Processing food images (16x16):")
    for filename, name in FOOD_IMAGES:
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  WARNING: {filename} not found, skipping")
            continue
        data = process_image(filepath, TREAT_W, TREAT_H, name)
        sprites.append((name, data, TREAT_W, TREAT_H))
    
    # Process sponge
    print("\nProcessing sponge image (20x14):")
    sponge_path = os.path.join(UPLOAD_DIR, SPONGE_IMAGE[0])
    if os.path.exists(sponge_path):
        sponge_data = process_image(sponge_path, SPONGE_W, SPONGE_H, "sponge")
    else:
        print(f"  WARNING: sponge image not found!")
        sponge_data = [FUR_RGB565] * (SPONGE_W * SPONGE_H)
    
    # Generate C header
    print(f"\nGenerating header: {HEADER_PATH}")
    
    food_sprites = [s for s in sprites]
    
    lines = []
    lines.append("// Auto-generated treat & sponge sprites for ESP32 Tamagotchi")
    lines.append("// RGB565 pixel data, background = fur color 0x9CD3")
    lines.append("#pragma once")
    lines.append("#include <Arduino.h>")
    lines.append("")
    lines.append(f"#define TREAT_SPRITE_W {TREAT_W}")
    lines.append(f"#define TREAT_SPRITE_H {TREAT_H}")
    lines.append(f"#define SPONGE_SPRITE_W {SPONGE_W}")
    lines.append(f"#define SPONGE_SPRITE_H {SPONGE_H}")
    lines.append(f"#define NUM_TREAT_TYPES {len(food_sprites)}")
    lines.append(f"#define COLOR_TREAT_BG 0x{FUR_RGB565:04X}")
    lines.append("")
    
    # Each food sprite
    for name, data, w, h in food_sprites:
        lines.append(f"// {name} ({w}x{h})")
        lines.append(f"const uint16_t treat_{name}[{w*h}] PROGMEM = {{")
        hex_vals = [f"0x{v:04X}" for v in data]
        for i in range(0, len(hex_vals), 12):
            chunk = ", ".join(hex_vals[i:i+12])
            if i + 12 < len(hex_vals):
                lines.append(f"  {chunk},")
            else:
                lines.append(f"  {chunk}")
        lines.append("};")
        lines.append("")
    
    # Sponge sprite
    lines.append(f"// sponge ({SPONGE_W}x{SPONGE_H})")
    lines.append(f"const uint16_t sponge_sprite[{SPONGE_W*SPONGE_H}] PROGMEM = {{")
    hex_vals = [f"0x{v:04X}" for v in sponge_data]
    for i in range(0, len(hex_vals), 12):
        chunk = ", ".join(hex_vals[i:i+12])
        if i + 12 < len(hex_vals):
            lines.append(f"  {chunk},")
        else:
            lines.append(f"  {chunk}")
    lines.append("};")
    lines.append("")
    
    # Index array for treats
    treat_names = [f"treat_{name}" for name, _, _, _ in food_sprites]
    lines.append("// Index array for random treat selection")
    lines.append(f"const uint16_t* const treat_sprites[NUM_TREAT_TYPES] PROGMEM = {{")
    for i, tn in enumerate(treat_names):
        comma = "," if i < len(treat_names) - 1 else ""
        lines.append(f"  {tn}{comma}")
    lines.append("};")
    lines.append("")
    
    header_content = "\n".join(lines)
    
    os.makedirs(os.path.dirname(HEADER_PATH), exist_ok=True)
    with open(HEADER_PATH, "w") as f:
        f.write(header_content)
    
    file_size = os.path.getsize(HEADER_PATH)
    print(f"\nDone! Header: {file_size} bytes, {len(food_sprites)} treats + 1 sponge")

if __name__ == "__main__":
    main()
