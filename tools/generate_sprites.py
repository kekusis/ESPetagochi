"""
Generate crisp, color-palette-limited 32x32 pixel art treat sprites for ESP32 Tamagotchi.
Converts food photos into 32x32 retro pixel art sprites with tight bounding boxes,
limited color palette (16 colors, no dither), dark contour outline, and fur-color chroma key.
"""
import os
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

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

TREAT_W, TREAT_H = 32, 32
SPONGE_W, SPONGE_H = 20, 14

def rgb_to_rgb565(r, g, b):
    r, g, b = int(r), int(g), int(b)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

def make_crispy_pixel_art(im, target_w=32, target_h=32, max_colors=16, is_jpg=False):
    """Convert an arbitrary food image into crisp 32x32 retro pixel art with outline and limited palette."""
    im_rgba = im.convert('RGBA')
    arr = np.array(im_rgba)
    
    if is_jpg:
        is_bg = (arr[:, :, 0] < 35) & (arr[:, :, 1] < 35) & (arr[:, :, 2] < 35)
        arr[is_bg, 3] = 0
        im_rgba = Image.fromarray(arr, 'RGBA')
        fg = ~is_bg
    else:
        fg = arr[:, :, 3] > 60
        arr[~fg, 3] = 0
        im_rgba = Image.fromarray(arr, 'RGBA')
    
    # 1. Tight bounding box crop: removes all surrounding empty margin
    rows = np.where(np.any(fg, axis=1))[0]
    cols = np.where(np.any(fg, axis=0))[0]
    if len(rows) > 0 and len(cols) > 0:
        im_rgba = im_rgba.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1))
    
    # 2. Boost saturation and contrast so retro pixel details pop vibrantly
    rgb = im_rgba.convert('RGB')
    rgb = ImageEnhance.Color(rgb).enhance(1.4)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.3)
    alpha = im_rgba.split()[3]
    im_rgba = Image.merge('RGBA', (*rgb.split(), alpha))
    
    # 3. Fit into target canvas, maximizing size while leaving 1px margin for dark outline
    max_w, max_h = target_w - 2, target_h - 2
    w, h = im_rgba.size
    scale = min(max_w / w, max_h / h)
    new_w = max(4, int(round(w * scale)))
    new_h = max(4, int(round(h * scale)))
    
    scaled = im_rgba.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new('RGBA', (target_w, target_h), (0, 0, 0, 0))
    ox = (target_w - new_w) // 2
    oy = (target_h - new_h) // 2
    canvas.paste(scaled, (ox, oy), scaled)
    
    # 4. Generate 1px dark contour outline around the shape
    c_arr = np.array(canvas)
    mask_im = Image.fromarray((c_arr[:, :, 3] > 80).astype(np.uint8) * 255, mode='L')
    dilated_im = mask_im.filter(ImageFilter.MaxFilter(3))
    
    mask = np.array(mask_im) > 128
    dilated = np.array(dilated_im) > 128
    outline = dilated & ~mask
    
    # 5. Quantize foreground to limited palette without dithering for crisp pixel art clusters
    fg_rgb = canvas.convert('RGB')
    quantized = fg_rgb.quantize(colors=max_colors, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.NONE).convert('RGB')
    q_arr = np.array(quantized)
    
    # 6. Compose sprite on FUR_COLOR background
    final_arr = np.full((target_h, target_w, 3), FUR_COLOR, dtype=np.uint8)
    final_arr[outline] = [28, 24, 30]  # dark retro outline
    final_arr[mask] = q_arr[mask]      # crispy quantized food pixels
    
    # 7. Convert to RGB565 with collision avoidance against FUR_RGB565 chroma-key
    rgb565_data = []
    for y in range(target_h):
        for x in range(target_w):
            r, g, b = final_arr[y, x]
            val = rgb_to_rgb565(r, g, b)
            if (mask[y, x] or outline[y, x]) and val == FUR_RGB565:
                val = 0x9CD4  # shift by 1 bit so foreground is never chroma-keyed out
            rgb565_data.append(val)
            
    return rgb565_data

def main():
    print("=== Generating Crisp 32x32 Pixel Art Treats ===\n")
    
    sprites = []
    for filename, name in FOOD_IMAGES:
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  WARNING: {filename} not found, skipping")
            continue
        im = Image.open(filepath)
        data = make_crispy_pixel_art(im, TREAT_W, TREAT_H, max_colors=16, is_jpg=filename.endswith('.jpg'))
        sprites.append((name, data, TREAT_W, TREAT_H))
        print(f"  Processed {name:12}: {TREAT_W}x{TREAT_H} crisp pixel art")
        
    # Sponge sprite
    sponge_path = os.path.join(UPLOAD_DIR, SPONGE_IMAGE[0])
    if os.path.exists(sponge_path):
        im = Image.open(sponge_path)
        sponge_data = make_crispy_pixel_art(im, SPONGE_W, SPONGE_H, max_colors=12, is_jpg=False)
    else:
        sponge_data = [FUR_RGB565] * (SPONGE_W * SPONGE_H)
    
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
    lines.append(f"#define NUM_TREAT_TYPES {len(sprites)}")
    lines.append(f"#define COLOR_TREAT_BG 0x{FUR_RGB565:04X}")
    lines.append("")
    
    for name, data, w, h in sprites:
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
        
    # Sponge
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
    
    # Index array
    treat_names = [f"treat_{name}" for name, _, _, _ in sprites]
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
        
    print(f"\nDone! Header generated at: {HEADER_PATH}")

if __name__ == "__main__":
    main()
