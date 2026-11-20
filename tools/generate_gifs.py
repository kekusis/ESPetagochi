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

def process_frames(src_path, crop_box, replace_all_white=False):
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
        
        if replace_all_white:
            # For sleeping animation: convert all white canvas pixels directly to fur
            # (No eye highlights needed since eyes are closed lines; eliminates canvas white under hat)
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    if (r > 230 and g > 230 and b > 230) or a < 128:
                        pixels[x, y] = (*FUR_COLOR, 255)
        else:
            # 1. Flood-fill outer white background from borders -> FUR_COLOR
            #    Preserves interior eye highlights/glints and red hearts completely
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
                # Only flood-fill white canvas (r, g, b all > 230). Never flood-fill colored art/hearts!
                if r > 230 and g > 230 and b > 230:
                    pixels[x, y] = (*FUR_COLOR, 255)
                    for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                        if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                            queue.append((nx, ny))
            
            # 2. Replace any transparent pixels with fur color
            for y in range(h):
                for x in range(w):
                    r, g, b, a = pixels[x, y]
                    if a < 128:
                        pixels[x, y] = (*FUR_COLOR, 255)
                        
        # 3. Resize to fill the entire 240x152 display canvas
        resized = cropped.resize((OUT_W, OUT_H), Image.Resampling.LANCZOS)
        frames.append(resized.convert('RGB'))
    return frames, durations

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(HEADER_PATH), exist_ok=True)
    
    anims = {}
    
    # Tight crop boxes so face stretches across the entire screen!
    crop_standard = (28, 13, 292, 180) # 264x167 -> aspect 1.58
    crop_hungry = (28, 10, 344, 210)   # Includes thought bubble -> aspect 1.58
    crop_happy = (20, 15, 335, 175)    # Includes red hearts on both sides
    crop_sleep = (25, 0, 355, 240)     # Includes nightcap and hand-drawn ZZZ
    crop_sleepy = (15, 5, 355, 215)    # Includes YAWN text at top right -> aspect 1.62
    
    # Check for latest happy GIF
    happy_file = os.path.join(DOWNLOADS_DIR, "happy(1).gif")
    if not os.path.exists(happy_file):
        happy_file = os.path.join(DOWNLOADS_DIR, "happy.gif")
        
    sleep_file = os.path.join(DOWNLOADS_DIR, "sleeping.gif")
    sleepy_file = os.path.join(DOWNLOADS_DIR, "sleepy.gif")
    squint_file = r"C:\Users\pezda\.gemini\antigravity\brain\8155fed1-7058-4969-ae78-4bfdb4de59ab\.user_uploaded\media_1795192970620_f26add97.png"
    
    # 1. Ingest User's Hand-Drawn Wiggly Paint GIFs with full-screen stretch
    anims['idle'] = process_frames(os.path.join(DOWNLOADS_DIR, "idle.gif"), crop_standard)
    
    # Slower, more relaxed playback for happy animation (190ms per frame)
    happy_frames, _ = process_frames(happy_file, crop_happy)
    anims['happy'] = (happy_frames, [190] * len(happy_frames))
    
    anims['hungry'] = process_frames(os.path.join(DOWNLOADS_DIR, "hungry.gif"), crop_hungry)
    anims['dirty'] = process_frames(os.path.join(DOWNLOADS_DIR, "dirty.gif"), crop_standard)
    anims['eating'] = process_frames(os.path.join(DOWNLOADS_DIR, "eating.gif"), crop_standard)
    
    # User's authentic hand-drawn sleeping animation with nightcap & ZZZ
    if os.path.exists(sleep_file):
        anims['sleeping'] = process_frames(sleep_file, crop_sleep, replace_all_white=True)
        print(f"Loaded user's authentic sleeping.gif: {len(anims['sleeping'][0])} frames (NO procedural Zs added)")
    else:
        anims['sleeping'] = ([f.copy() for f in happy_frames[:4]], [300]*4)
        
    # User's authentic sleepy (yawn) animation
    if os.path.exists(sleepy_file):
        anims['sleepy'] = process_frames(sleepy_file, crop_sleepy)
        print(f"Loaded user's authentic sleepy.gif: {len(anims['sleepy'][0])} frames")
    else:
        # Fallback to uploaded PNG
        uploaded_sleepy = r"C:\Users\pezda\.gemini\antigravity\brain\8155fed1-7058-4969-ae78-4bfdb4de59ab\.user_uploaded\media_1795192970620_34722153.png"
        if os.path.exists(uploaded_sleepy):
            sf, _ = process_frames(uploaded_sleepy, crop_sleepy)
            anims['sleepy'] = (sf * 2, [300, 300])
            print(f"Loaded user's uploaded sleepy image: {len(anims['sleepy'][0])} frames")
            
    # User's authentic squinting cat smile expression
    if os.path.exists(squint_file):
        sq_frames, _ = process_frames(squint_file, crop_standard)
        anims['squint'] = (sq_frames * 2, [350, 350])
        print(f"Loaded user's authentic squinting expression: {len(anims['squint'][0])} frames")
    
    for name in ['idle', 'happy', 'hungry', 'dirty', 'eating']:
        print(f"Loaded and stretched {name}.gif: {len(anims[name][0])} frames")
        
    idle_frames, idle_dur = anims['idle']
    
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
    
    # Playing: BALL REMOVED! Pure character animation
    play_frames = [f.copy() for f in idle_frames]
    anims['playing'] = (play_frames, idle_dur)
    
    # 20-Degree Rotated Idle Animations for PLAY minigame (Tilts directly toward active arrow!)
    anims['play_left'] = ([f.rotate(20, resample=Image.BICUBIC, fillcolor=FUR_COLOR) for f in idle_frames], idle_dur)
    anims['play_right'] = ([f.rotate(-20, resample=Image.BICUBIC, fillcolor=FUR_COLOR) for f in idle_frames], idle_dur)
    
    # 3. Export to assets/gifs and build C header
    header_content = """// Auto-generated pet animations header for ESP32 Tamagotchi
// Full-screen stretched hand-drawn character face with darker gray fur
#pragma once
#include <Arduino.h>

"""
    for name, (frames, durations) in anims.items():
        w, h = frames[0].size
        # Generate global palette from ALL frames stitched together
        # This guarantees that unique colors (like red hearts in later frames) are never quantized to brown!
        combined = Image.new('RGB', (w * len(frames), h))
        for i, f in enumerate(frames):
            combined.paste(f, (i * w, 0))
        pal_img = combined.convert('P', palette=Image.ADAPTIVE, colors=128)
        
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
