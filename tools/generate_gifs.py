import os
from PIL import Image, ImageSequence, ImageDraw
from collections import deque

DOWNLOADS_DIR = r"C:\Users\pezda\Downloads"
OUTPUT_DIR = r"C:\Users\pezda\Desktop\ESPetagochi-main\assets\gifs"
HEADER_PATH = r"C:\Users\pezda\Desktop\ESPetagochi-main\firmware\include\pet_gifs.h"

# Darker Gray Fur Color (matches 0x9CD3 in RGB565 -> RGB 155, 155, 155)
FUR_COLOR = (155, 155, 155)
# Full screen width and height between HUD bars (240x152)
OUT_W, OUT_H = 240, 152

def process_frames(src_path, crop_box):
    src = Image.open(src_path)
    frames = []
    durations = []
    
    for frame in ImageSequence.Iterator(src):
        duration = frame.info.get('duration', 100)
        durations.append(max(80, duration))
        
        rgba = frame.convert('RGBA')
        cropped = rgba.crop(crop_box)
        
        w, h = cropped.size
        pixels = cropped.load()
        
        # 1. Flood-fill outer white background from borders -> FUR_COLOR
        #    Preserves interior eye highlights/glints completely
        visited = set()
        queue = deque()
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
            if r > 230 and g > 230 and b > 230:
                pixels[x, y] = (*FUR_COLOR, 255)
                for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                        queue.append((nx, ny))
        
        # 2. Replace any transparent or stray background pixels with fur color
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if a < 128:
                    pixels[x, y] = (*FUR_COLOR, 255)
                    
        # 3. Resize to fill the entire 240x152 display canvas
        resized = cropped.resize((OUT_W, OUT_H), Image.Resampling.NEAREST)
        frames.append(resized.convert('RGB'))
    return frames, durations

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(HEADER_PATH), exist_ok=True)
    
    anims = {}
    
    # Tight crop boxes so face stretches across the entire screen!
    crop_standard = (28, 13, 292, 180) # 264x167 -> aspect 1.58
    crop_hungry = (28, 10, 344, 210)   # Includes thought bubble -> aspect 1.58
    
    # 1. Ingest User's Hand-Drawn Wiggly Paint GIFs with full-screen stretch
    anims['idle'] = process_frames(os.path.join(DOWNLOADS_DIR, "idle.gif"), crop_standard)
    anims['happy'] = process_frames(os.path.join(DOWNLOADS_DIR, "happy.gif"), crop_standard)
    anims['hungry'] = process_frames(os.path.join(DOWNLOADS_DIR, "hungry.gif"), crop_hungry)
    anims['dirty'] = process_frames(os.path.join(DOWNLOADS_DIR, "dirty.gif"), crop_standard)
    anims['eating'] = process_frames(os.path.join(DOWNLOADS_DIR, "eating.gif"), crop_standard)
    
    for name in ['idle', 'happy', 'hungry', 'dirty', 'eating']:
        print(f"Loaded and stretched {name}.gif: {len(anims[name][0])} frames")
        
    # 2. Derive the 3 remaining animations (sleeping, washing, playing) scaled up
    happy_frames, happy_dur = anims['happy']
    idle_frames, idle_dur = anims['idle']
    
    # Sleeping (gentle closed eyes face with drifting Zzz)
    sleep_frames = []
    for i in range(4):
        f = happy_frames[i % len(happy_frames)].copy()
        d = ImageDraw.Draw(f)
        zy = 24 - (i * 4)
        d.text((188, zy + 8), "z", fill=(100, 120, 180))
        d.text((200, zy), "Z", fill=(70, 90, 160))
        sleep_frames.append(f)
    anims['sleeping'] = (sleep_frames, [300]*4)
    
    # Washing (joyful face with floating sparkling bubbles)
    wash_frames = []
    for i in range(4):
        f = happy_frames[(i*2) % len(happy_frames)].copy()
        d = ImageDraw.Draw(f)
        for bx, by, r in [(16, 26 + i*3, 14), (206, 20 - i*3, 16), (20, 110, 10), (204, 105, 12)]:
            d.ellipse([bx, by, bx+r, by+r], outline=(80, 180, 240), fill=(160, 215, 245), width=2)
            d.point((bx+3, by+3), fill=(255, 255, 255))
        wash_frames.append(f)
    anims['washing'] = (wash_frames, [180]*4)
    
    # Playing (content face with bouncing ball)
    play_frames = []
    for i in range(6):
        f = idle_frames[i % len(idle_frames)].copy()
        d = ImageDraw.Draw(f)
        ball_x = 195 + (i * 5)
        ball_y = 105 - [0, 22, 36, 28, 14, 0][i]
        d.ellipse([ball_x-10, ball_y-10, ball_x+10, ball_y+10], fill=(255, 80, 60), outline=(180, 40, 30), width=2)
        play_frames.append(f)
    anims['playing'] = (play_frames, [140]*6)
    
    # 3. Export to assets/gifs and build C header
    header_content = """// Auto-generated pet animations header for ESP32 Tamagotchi
// Full-screen stretched hand-drawn character face with darker gray fur
#pragma once
#include <Arduino.h>

"""
    for name, (frames, durations) in anims.items():
        pal_img = frames[0].convert('P', palette=Image.ADAPTIVE, colors=64)
        q_frames = [f.quantize(palette=pal_img, dither=Image.Dither.NONE) for f in frames]
        gif_file = os.path.join(OUTPUT_DIR, f"{name}.gif")
        
        q_frames[0].save(
            gif_file,
            save_all=True,
            append_images=q_frames[1:],
            duration=durations,
            loop=0,
            optimize=True
        )
        sz = os.path.getsize(gif_file)
        print(f"Generated {name}.gif ({sz} bytes, {len(frames)} frames)")
        
        with open(gif_file, "rb") as f:
            data = f.read()
            
        header_content += f"// {name}.gif ({len(data)} bytes)\n"
        header_content += f"const uint8_t gif_{name}[] PROGMEM = {{\n  "
        hex_vals = [f"0x{b:02X}" for b in data]
        for i in range(0, len(hex_vals), 16):
            header_content += ", ".join(hex_vals[i:i+16]) + (",\n  " if i+16 < len(hex_vals) else "\n};\n")
        header_content += f"const size_t gif_{name}_len = sizeof(gif_{name});\n\n"
        
    with open(HEADER_PATH, "w") as f:
        f.write(header_content)
    print(f"Saved header at {HEADER_PATH}")

if __name__ == "__main__":
    main()
