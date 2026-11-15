import os
from PIL import Image, ImageDraw

OUTPUT_DIR = r"C:\Users\pezda\Desktop\ESPetagochi-main\assets\gifs"
HEADER_PATH = r"C:\Users\pezda\Desktop\ESPetagochi-main\firmware\include\pet_gifs.h"

# Reference character color palette
FUR_BG = (185, 180, 172)        # Warm grayish-taupe fur (RGB565: 0xBDF5)
HAIR_BASE = (215, 182, 115)     # Golden-blonde base
HAIR_SHADOW = (175, 140, 85)    # Golden hair shadow
HAIR_LIGHT = (235, 205, 145)    # Golden hair highlight
HAIR_OUTLINE = (135, 105, 60)   # Hair strand outline
EYEBROW_COLOR = (165, 135, 90)  # Tan eyebrow spots
EYEBROW_OUTLINE = (125, 95, 55)

EYE_LASH = (20, 25, 30)         # Winged dark lash line
EYE_DARK = (45, 85, 120)        # Deep slate blue
EYE_MID = (65, 125, 165)        # Mid slate cyan
EYE_LIGHT = (95, 165, 210)      # Vivid cyan iris bottom
EYE_GLINT = (255, 255, 255)     # White dual sparkle glints

NOSE_COLOR = (45, 45, 50)       # Dark nose
MOUTH_LINE = (35, 35, 40)
MOUTH_TONGUE = (235, 110, 130)  # Pink tongue
BLUSH_COLOR = (235, 145, 160)   # Cute cheek blush

W, H = 240, 154

def draw_hair(d, sway=0):
    # Left hair layers
    d.polygon([(-5, -5), (28+sway, -5), (22+sway, 50), (32+sway, 90), (18+sway, 140), (25+sway, 160), (-5, 160)], fill=HAIR_BASE, outline=HAIR_OUTLINE)
    d.line([(8+sway, 0), (12+sway, 60), (6+sway, 120)], fill=HAIR_LIGHT, width=2)
    d.line([(20+sway, 30), (24+sway, 80), (16+sway, 150)], fill=HAIR_SHADOW, width=2)

    # Right hair layers
    d.polygon([(245, -5), (212+sway, -5), (218+sway, 50), (208+sway, 90), (222+sway, 140), (215+sway, 160), (245, 160)], fill=HAIR_BASE, outline=HAIR_OUTLINE)
    d.line([(232+sway, 0), (228+sway, 60), (234+sway, 120)], fill=HAIR_LIGHT, width=2)
    d.line([(220+sway, 30), (216+sway, 80), (224+sway, 150)], fill=HAIR_SHADOW, width=2)

    # Top Bangs framing forehead
    d.polygon([(26, -5), (85, -5), (78+sway, 38), (62+sway, 42), (46+sway, 28)], fill=HAIR_BASE, outline=HAIR_OUTLINE)
    d.polygon([(75, -5), (125, -5), (114+sway, 46), (98+sway, 48), (80+sway, 30)], fill=HAIR_BASE, outline=HAIR_OUTLINE)
    d.polygon([(115, -5), (165, -5), (154+sway, 48), (136+sway, 46), (118+sway, 28)], fill=HAIR_BASE, outline=HAIR_OUTLINE)
    d.polygon([(155, -5), (214, -5), (194+sway, 28), (180+sway, 42), (162+sway, 38)], fill=HAIR_BASE, outline=HAIR_OUTLINE)
    
    # Bangs highlights
    d.line([(55+sway, 5), (66+sway, 32)], fill=HAIR_LIGHT, width=2)
    d.line([(95+sway, 5), (104+sway, 36)], fill=HAIR_LIGHT, width=2)
    d.line([(135+sway, 5), (142+sway, 36)], fill=HAIR_LIGHT, width=2)
    d.line([(175+sway, 5), (182+sway, 30)], fill=HAIR_LIGHT, width=2)

def draw_face(eye_state='open', mouth_state='smile', y_off=0, x_off=0, hair_sway=0, blush=False, dirt=False, food_stage=-1, nightcap=False, zzz_offset=-1, sparkles=False, ball_pos=None, thought_food=False, wash_bubbles=-1):
    im = Image.new('RGB', (W, H), FUR_BG)
    d = ImageDraw.Draw(im)
    cy = 82 + y_off
    cx_l, cx_r = 74 + x_off, 166 + x_off
    draw_hair(d, hair_sway)
    
    def eyebrow(bx, by, droop=False):
        dy = 4 if droop else 0
        d.ellipse([bx-10, by-6+dy, bx+10, by+6+dy], fill=EYEBROW_COLOR, outline=EYEBROW_OUTLINE, width=1)
        d.ellipse([bx-7, by-4+dy, bx+3, by+1+dy], fill=HAIR_LIGHT)
        
    droop = (eye_state == 'sad')
    eyebrow(cx_l, cy - 30, droop)
    eyebrow(cx_r, cy - 30, droop)
    
    def eye(ex, ey, state='open'):
        if state == 'blink' or state == 'happy' or state == 'sleep':
            d.arc([ex-18, ey-8, ex+18, ey+16], 190, 350, fill=EYE_LASH, width=4)
            d.arc([ex-16, ey-6, ex+16, ey+14], 190, 350, fill=EYE_LASH, width=3)
            return
        if state == 'wink':
            d.line([ex-16, ey, ex+16, ey], fill=EYE_LASH, width=4)
            return
        ex0, ey0, ex1, ey1 = ex-16, ey-22, ex+16, ey+22
        d.ellipse([ex0, ey0, ex1, ey1], fill=EYE_DARK)
        d.ellipse([ex0+2, ey0+10, ex1-2, ey1-2], fill=EYE_MID)
        d.ellipse([ex0+5, ey0+22, ex1-5, ey1-4], fill=EYE_LIGHT)
        d.ellipse([ex-5, ey-8, ex+5, ey+8], fill=(20, 30, 40))
        d.arc([ex0-4, ey0-4, ex1+4, ey0+20], 190, 350, fill=EYE_LASH, width=5)
        if ex < 120:
            d.line([ex0-3, ey0+6, ex0-8, ey0+4], fill=EYE_LASH, width=3)
        else:
            d.line([ex1+3, ey0+6, ex1+8, ey0+4], fill=EYE_LASH, width=3)
        d.ellipse([ex-9, ey-14, ex-3, ey-8], fill=EYE_GLINT)
        d.ellipse([ex+4, ey+6, ex+8, ey+10], fill=EYE_GLINT)
        if state == 'sad':
            d.ellipse([ex-4, ey+16, ex+4, ey+24], fill=(130, 200, 245), outline=(255, 255, 255))
            
    eye(cx_l, cy, 'wink' if eye_state == 'wink' else eye_state)
    eye(cx_r, cy, 'open' if eye_state == 'wink' else eye_state)
    
    if blush:
        d.ellipse([cx_l - 24, cy + 12, cx_l - 6, cy + 22], fill=BLUSH_COLOR)
        d.ellipse([cx_r + 6, cy + 12, cx_r + 24, cy + 22], fill=BLUSH_COLOR)
        
    if dirt:
        d.ellipse([cx_l + 10, cy + 10, cx_l + 26, cy + 20], fill=(100, 75, 55))
        d.ellipse([cx_r - 26, cy + 14, cx_r - 10, cy + 22], fill=(100, 75, 55))
        d.ellipse([112, cy - 24, 128, cy - 14], fill=(100, 75, 55))
        d.arc([55, 20, 75, 45], 0, 180, fill=(90, 160, 70), width=2)
        d.arc([165, 18, 185, 43], 0, 180, fill=(90, 160, 70), width=2)
        
    ny = cy + 26
    nx = 120 + x_off
    d.polygon([(nx-5, ny), (nx+5, ny), (nx, ny+6)], fill=NOSE_COLOR)
    d.line([(nx, ny+6), (nx, ny+10)], fill=NOSE_COLOR, width=2)
    
    my = ny + 10
    if mouth_state == 'smile':
        d.arc([nx-16, my-4, nx, my+10], 10, 170, fill=MOUTH_LINE, width=2)
        d.arc([nx, my-4, nx+16, my+10], 10, 170, fill=MOUTH_LINE, width=2)
        d.polygon([(nx-2, my+3), (nx+4, my+3), (nx+1, my+8)], fill=(255, 255, 255), outline=MOUTH_LINE)
    elif mouth_state == 'open_grin':
        d.chord([nx-18, my-2, nx+18, my+18], 0, 180, fill=(160, 45, 60), outline=MOUTH_LINE, width=2)
        d.ellipse([nx-8, my+7, nx+8, my+16], fill=MOUTH_TONGUE)
        d.polygon([(nx-14, my-1), (nx-4, my-1), (nx-9, my+5)], fill=(255, 255, 255))
        d.polygon([(nx+4, my-1), (nx+14, my-1), (nx+9, my+5)], fill=(255, 255, 255))
    elif mouth_state == 'sad':
        d.arc([nx-14, my+2, nx+14, my+16], 180, 360, fill=MOUTH_LINE, width=3)
    elif mouth_state == 'tongue':
        d.arc([nx-14, my-4, nx+14, my+8], 0, 180, fill=MOUTH_LINE, width=2)
        d.chord([nx-6, my+3, nx+6, my+15], 0, 180, fill=MOUTH_TONGUE, outline=MOUTH_LINE, width=2)
    elif mouth_state == 'chomp':
        d.chord([nx-16, my-4, nx+16, my+16], 0, 180, fill=(160, 45, 60), outline=MOUTH_LINE, width=2)
        d.polygon([(nx-10, my-3), (nx-2, my-3), (nx-6, my+4)], fill=(255, 255, 255))
        d.polygon([(nx+2, my-3), (nx+10, my-3), (nx+6, my+4)], fill=(255, 255, 255))
        
    if food_stage >= 0:
        fx = nx + [28, 14, 4, 18][food_stage % 4]
        fy = my + [0, 2, 4, 2][food_stage % 4]
        d.ellipse([fx-12, fy-8, fx+12, fy+8], fill=(240, 160, 50), outline=(160, 90, 20), width=2)
        d.rectangle([fx-10, fy-2, fx+10, fy+2], fill=(90, 180, 70))
        if food_stage % 2 == 1:
            d.rectangle([fx-16, fy+8, fx-13, fy+11], fill=(240, 160, 50))
            d.rectangle([fx+12, fy+6, fx+15, fy+9], fill=(240, 160, 50))
            
    if nightcap:
        d.polygon([(60, 32), (105, 14), (124, 44)], fill=(70, 110, 200), outline=(40, 70, 150), width=2)
        d.ellipse([118, 38, 134, 54], fill=(255, 255, 255))
        
    if zzz_offset >= 0:
        zy = 24 - (zzz_offset * 4)
        d.text((188, zy + 8), 'z', fill=(110, 140, 210))
        d.text((200, zy), 'Z', fill=(75, 105, 185))
        
    if sparkles:
        for sx, sy in [(36, 40), (204, 35), (32, 115), (208, 110)]:
            d.polygon([(sx, sy-6), (sx+2, sy-2), (sx+6, sy), (sx+2, sy+2), (sx, sy+6), (sx-2, sy+2), (sx-6, sy), (sx-2, sy-2)], fill=(255, 230, 120))
            d.point((sx, sy), fill=(255, 255, 255))
            
    if ball_pos:
        bx, by = ball_pos
        d.ellipse([bx-12, by-12, bx+12, by+12], fill=(255, 75, 60), outline=(180, 35, 25), width=2)
        d.arc([bx-12, by-12, bx+12, by+12], 45, 135, fill=(255, 255, 255), width=2)
        
    if thought_food:
        bx, by = 195, 24
        d.ellipse([bx-4, by+12, bx+4, by+20], fill=(210, 210, 225), outline=(150, 150, 170))
        d.ellipse([bx+6, by+4, bx+16, by+14], fill=(210, 210, 225), outline=(150, 150, 170))
        d.ellipse([bx-6, by-16, bx+34, by+12], fill=(245, 245, 255), outline=(150, 150, 170))
        d.ellipse([bx+2, by-10, bx+18, by+2], fill=(235, 140, 40), outline=(160, 80, 20))
        d.line([bx+16, by-2, bx+26, by+6], fill=(230, 230, 230), width=4)
        
    if wash_bubbles >= 0:
        for bx, by, r in [(20, 24 + wash_bubbles*3, 14), (210, 18 - wash_bubbles*3, 16), (24, 114, 10), (208, 108, 12)]:
            d.ellipse([bx, by, bx+r, by+r], outline=(80, 180, 240), fill=(160, 215, 245), width=2)
            d.point((bx+3, by+3), fill=(255, 255, 255))
            
    return im

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(HEADER_PATH), exist_ok=True)

    anims = {
        'idle': ([draw_face(eye_state='open', mouth_state='smile', y_off=0, hair_sway=0),
                  draw_face(eye_state='open', mouth_state='smile', y_off=2, hair_sway=1),
                  draw_face(eye_state='blink', mouth_state='smile', y_off=0, hair_sway=0),
                  draw_face(eye_state='open', mouth_state='smile', y_off=1, hair_sway=-1)], [260]*4),
                  
        'happy': ([draw_face(eye_state='happy', mouth_state='open_grin', y_off=-2, blush=True, sparkles=True),
                   draw_face(eye_state='happy', mouth_state='open_grin', y_off=-6, blush=True, sparkles=True),
                   draw_face(eye_state='happy', mouth_state='open_grin', y_off=-3, blush=True, sparkles=True),
                   draw_face(eye_state='happy', mouth_state='smile', y_off=1, blush=True, sparkles=False)], [180]*4),
                   
        'hungry': ([draw_face(eye_state='sad', mouth_state='sad', x_off=-2, y_off=2, thought_food=True),
                    draw_face(eye_state='sad', mouth_state='sad', x_off=2, y_off=2, thought_food=True),
                    draw_face(eye_state='sad', mouth_state='sad', x_off=-1, y_off=3, thought_food=True),
                    draw_face(eye_state='sad', mouth_state='sad', x_off=1, y_off=2, thought_food=True)], [220]*4),
                    
        'dirty': ([draw_face(eye_state='open', mouth_state='tongue', y_off=2, dirt=True),
                   draw_face(eye_state='blink', mouth_state='tongue', y_off=3, dirt=True),
                   draw_face(eye_state='open', mouth_state='tongue', y_off=2, dirt=True),
                   draw_face(eye_state='open', mouth_state='tongue', y_off=1, dirt=True)], [240]*4),
                   
        'eating': ([draw_face(eye_state='open', mouth_state='chomp', food_stage=0, blush=True),
                    draw_face(eye_state='happy', mouth_state='smile', food_stage=1, blush=True),
                    draw_face(eye_state='open', mouth_state='chomp', food_stage=2, blush=True),
                    draw_face(eye_state='happy', mouth_state='smile', food_stage=3, blush=True)], [160]*4),
                    
        'washing': ([draw_face(eye_state='happy', mouth_state='open_grin', sparkles=True, wash_bubbles=0),
                     draw_face(eye_state='happy', mouth_state='open_grin', sparkles=True, wash_bubbles=1),
                     draw_face(eye_state='happy', mouth_state='smile', sparkles=True, wash_bubbles=2),
                     draw_face(eye_state='happy', mouth_state='open_grin', sparkles=True, wash_bubbles=3)], [180]*4),
                     
        'sleeping': ([draw_face(eye_state='sleep', mouth_state='smile', y_off=2, nightcap=True, zzz_offset=0),
                      draw_face(eye_state='sleep', mouth_state='smile', y_off=4, nightcap=True, zzz_offset=1),
                      draw_face(eye_state='sleep', mouth_state='smile', y_off=3, nightcap=True, zzz_offset=2),
                      draw_face(eye_state='sleep', mouth_state='smile', y_off=1, nightcap=True, zzz_offset=3)], [320]*4),
                      
        'playing': ([draw_face(eye_state='wink', mouth_state='open_grin', y_off=-2, ball_pos=(205, 110)),
                     draw_face(eye_state='open', mouth_state='open_grin', y_off=-6, ball_pos=(210, 80)),
                     draw_face(eye_state='happy', mouth_state='open_grin', y_off=-4, ball_pos=(215, 60)),
                     draw_face(eye_state='wink', mouth_state='smile', y_off=0, ball_pos=(212, 75)),
                     draw_face(eye_state='open', mouth_state='open_grin', y_off=-3, ball_pos=(208, 95)),
                     draw_face(eye_state='happy', mouth_state='smile', y_off=1, ball_pos=(205, 110))], [140]*6)
    }

    header_content = """// Auto-generated Kekusis character animations header for ESP32 Tamagotchi
// Reference illustration character with warm taupe fur, golden blonde bangs & cyan eyes
#pragma once
#include <Arduino.h>

"""
    tot_bytes = 0
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
        tot_bytes += sz
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
    print(f"Total GIF size: {tot_bytes} bytes across 8 animations.")
    print(f"Saved header at {HEADER_PATH}")

if __name__ == "__main__":
    main()
