import os
import random
import math
from PIL import Image, ImageDraw

OUTPUT_DIR = r"C:\Users\pezda\Desktop\ESPetagochi-main\assets\gifs"
HEADER_PATH = r"C:\Users\pezda\Desktop\ESPetagochi-main\firmware\include\pet_gifs.h"

# Display dimensions
W, H = 240, 154

# Palette
FUR_BG = (185, 180, 172)        # Warm grayish-taupe fur background (RGB565: 0xBDF5)
EYEBROW_COLOR = (190, 155, 100) # Tan bean eyebrow spots
EYE_BLUE = (60, 115, 180)       # Rich hand-drawn blue iris
EYE_DARK = (20, 35, 60)         # Dark pupil center
LINE_COLOR = (20, 20, 25)       # Charcoal/ink line
BLUSH_COLOR = (225, 140, 150)   # Soft cheek blush
TONGUE_COLOR = (235, 110, 130)  # Pink tongue

def rough_polygon(draw, cx, cy, rx, ry, fill, outline=None, pts=16, jitter=1.4, rng=None):
    if rng is None:
        rng = random.Random()
    coords = []
    for i in range(pts):
        angle = 2 * math.pi * i / pts
        r_x = rx + rng.uniform(-jitter, jitter)
        r_y = ry + rng.uniform(-jitter, jitter)
        x = cx + r_x * math.cos(angle)
        y = cy + r_y * math.sin(angle)
        coords.append((x, y))
    draw.polygon(coords, fill=fill, outline=outline)

def rough_stroke(draw, pts, fill, width=4, jitter=1.2, rng=None):
    if rng is None:
        rng = random.Random()
    j_pts = []
    for (x, y) in pts:
        jx = x + rng.uniform(-jitter, jitter)
        jy = y + rng.uniform(-jitter, jitter)
        j_pts.append((jx, jy))
    for i in range(len(j_pts) - 1):
        w = max(2, int(width + rng.uniform(-0.6, 0.6)))
        draw.line([j_pts[i], j_pts[i+1]], fill=fill, width=w)
        r = w / 2.0
        draw.ellipse([j_pts[i][0]-r, j_pts[i][1]-r, j_pts[i][0]+r, j_pts[i][1]+r], fill=fill)

def arc_points(cx, cy, rx, ry, start_angle, end_angle, steps=10):
    pts = []
    for i in range(steps + 1):
        t = start_angle + (end_angle - start_angle) * (i / float(steps))
        x = cx + rx * math.cos(t)
        y = cy + ry * math.sin(t)
        pts.append((x, y))
    return pts

def line_points(x0, y0, x1, y1, steps=8):
    return [(x0 + (x1 - x0) * (i / float(steps)), y0 + (y1 - y0) * (i / float(steps))) for i in range(steps + 1)]

def draw_wiggly_frame(
    seed,
    eye_style='idle',       # 'idle', 'blink', 'happy', 'sad', 'wink', 'sleep'
    mouth_style='cat',      # 'cat', 'open_cat', 'sad', 'tongue', 'chew_open', 'chew_closed'
    y_off=0, x_off=0,
    blush=False,
    dirt=False,
    thought_food=False,
    zzz_step=-1,
    bubbles_step=-1,
    ball_step=-1,
    chew_crumb=False
):
    rng = random.Random(seed)
    im = Image.new('RGB', (W, H), FUR_BG)
    d = ImageDraw.Draw(im)

    cx_l = 75 + x_off
    cx_r = 165 + x_off
    cy = 70 + y_off

    # 1. Eyebrows (Tactile, wobbly organic tan spots)
    if eye_style == 'sad':
        rough_polygon(d, cx_l, cy - 34, 18, 9, fill=EYEBROW_COLOR, pts=16, jitter=1.5, rng=rng)
        rough_polygon(d, cx_r, cy - 34, 18, 9, fill=EYEBROW_COLOR, pts=16, jitter=1.5, rng=rng)
    elif eye_style == 'happy':
        rough_polygon(d, cx_l, cy - 38, 18, 8, fill=EYEBROW_COLOR, pts=16, jitter=1.5, rng=rng)
        rough_polygon(d, cx_r, cy - 38, 18, 8, fill=EYEBROW_COLOR, pts=16, jitter=1.5, rng=rng)
    else:
        rough_polygon(d, cx_l, cy - 32, 18, 8, fill=EYEBROW_COLOR, pts=16, jitter=1.5, rng=rng)
        rough_polygon(d, cx_r, cy - 32, 18, 8, fill=EYEBROW_COLOR, pts=16, jitter=1.5, rng=rng)

    # 2. Eyes
    def draw_eye(ex, ey, style, is_right=False):
        if style == 'happy':
            # ^ curved smiling arch
            pts = arc_points(ex, ey + 4, 20, 15, math.pi * 1.1, math.pi * 1.9, steps=10)
            rough_stroke(d, pts, fill=LINE_COLOR, width=5, jitter=1.3, rng=rng)
            return
        elif style == 'sleep':
            # u curved sleeping arch
            pts = arc_points(ex, ey - 4, 20, 14, math.pi * 0.1, math.pi * 0.9, steps=10)
            rough_stroke(d, pts, fill=LINE_COLOR, width=5, jitter=1.3, rng=rng)
            return
        elif style == 'blink':
            pts = line_points(ex - 22, ey, ex + 22, ey, steps=8)
            rough_stroke(d, pts, fill=LINE_COLOR, width=5, jitter=1.2, rng=rng)
            return
        elif style == 'wink' and not is_right:
            # > winking shape
            pts1 = line_points(ex - 18, ey - 10, ex + 8, ey, steps=6)
            pts2 = line_points(ex + 8, ey, ex - 18, ey + 10, steps=6)
            rough_stroke(d, pts1, fill=LINE_COLOR, width=5, jitter=1.2, rng=rng)
            rough_stroke(d, pts2, fill=LINE_COLOR, width=5, jitter=1.2, rng=rng)
            return

        # Open Eye: Blue iris underneath thick rough top lash line
        iris_pts = []
        for i in range(12):
            t = math.pi * (i / 11.0)
            rx = 22 + rng.uniform(-1.2, 1.2)
            ry = 22 + rng.uniform(-1.2, 1.2)
            iris_pts.append((ex + rx * math.cos(t), ey - 8 + ry * math.sin(t)))
        d.polygon(iris_pts, fill=EYE_BLUE)

        # Dark pupil center
        pupil_pts = []
        for i in range(10):
            t = math.pi * (i / 9.0)
            rx = 12 + rng.uniform(-1.0, 1.0)
            ry = 14 + rng.uniform(-1.0, 1.0)
            pupil_pts.append((ex + rx * math.cos(t), ey - 4 + ry * math.sin(t)))
        d.polygon(pupil_pts, fill=EYE_DARK)

        # White glint (organic spot)
        rough_polygon(d, ex - 10, ey - 1, 5, 5, fill=(255, 255, 255), pts=8, jitter=0.8, rng=rng)
        rough_polygon(d, ex + 6, ey + 7, 3, 3, fill=(255, 255, 255), pts=6, jitter=0.6, rng=rng)

        # Upper thick eyelash line
        if style == 'sad':
            pts = line_points(ex - 24, ey - 6, ex + 24, ey + 2 if not is_right else ey - 8, steps=8)
        else:
            pts = line_points(ex - 26, ey - 10, ex + 26, ey - 10, steps=8)
            if is_right:
                pts.append((ex + 32, ey - 14))
            else:
                pts.insert(0, (ex - 32, ey - 14))
        rough_stroke(d, pts, fill=LINE_COLOR, width=5, jitter=1.2, rng=rng)

    draw_eye(cx_l, cy, 'wink' if eye_style == 'wink' else eye_style, is_right=False)
    draw_eye(cx_r, cy, 'idle' if eye_style == 'wink' else eye_style, is_right=True)

    # 3. Blush
    if blush:
        rough_polygon(d, cx_l - 12, cy + 22, 12, 6, fill=BLUSH_COLOR, pts=10, jitter=1.5, rng=rng)
        rough_polygon(d, cx_r + 12, cy + 22, 12, 6, fill=BLUSH_COLOR, pts=10, jitter=1.5, rng=rng)

    # 4. Dirt Smudges
    if dirt:
        rough_polygon(d, cx_l - 12, cy + 20, 8, 5, fill=(120, 95, 75), pts=8, jitter=1.5, rng=rng)
        rough_polygon(d, cx_r + 12, cy + 18, 9, 5, fill=(120, 95, 75), pts=8, jitter=1.5, rng=rng)
        rough_polygon(d, 120, cy - 24, 7, 5, fill=(120, 95, 75), pts=8, jitter=1.5, rng=rng)
        # Little doodle squiggles
        d.line([(52, 26), (60, 32), (66, 26)], fill=(110, 150, 90), width=2)
        d.line([(174, 24), (182, 30), (188, 24)], fill=(110, 150, 90), width=2)

    # 5. Nose & Cat Mouth :3
    nx = 120 + x_off
    ny = cy + 34
    rough_polygon(d, nx, ny + 3, 8, 4, fill=LINE_COLOR, pts=8, jitter=1.0, rng=rng)
    rough_stroke(d, line_points(nx, ny + 5, nx, ny + 13, steps=4), fill=LINE_COLOR, width=3, jitter=0.8, rng=rng)

    my = ny + 13
    if mouth_style == 'cat':
        pts_l = arc_points(nx - 9, my, 9, 8, math.pi * 0.1, math.pi * 0.9, steps=8)
        pts_r = arc_points(nx + 9, my, 9, 8, math.pi * 0.1, math.pi * 0.9, steps=8)
        rough_stroke(d, pts_l, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
        rough_stroke(d, pts_r, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
    elif mouth_style == 'open_cat':
        mouth_pts = arc_points(nx, my + 2, 16, 12, 0, math.pi, steps=10)
        d.polygon(mouth_pts, fill=(170, 50, 65))
        rough_polygon(d, nx, my + 8, 8, 5, fill=TONGUE_COLOR, pts=8, jitter=1.0, rng=rng)
        # Little fang
        fang = [(nx - 8, my + 1), (nx - 3, my + 1), (nx - 5, my + 6)]
        d.polygon(fang, fill=(255, 255, 255))
        rough_stroke(d, mouth_pts, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
        rough_stroke(d, line_points(nx - 16, my + 2, nx + 16, my + 2, steps=6), fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
    elif mouth_style == 'tongue':
        pts_l = arc_points(nx - 9, my, 9, 8, math.pi * 0.1, math.pi * 0.9, steps=8)
        pts_r = arc_points(nx + 9, my, 9, 8, math.pi * 0.1, math.pi * 0.9, steps=8)
        rough_polygon(d, nx, my + 8, 7, 7, fill=TONGUE_COLOR, pts=10, jitter=1.2, rng=rng)
        rough_stroke(d, pts_l, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
        rough_stroke(d, pts_r, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
    elif mouth_style == 'sad':
        pts = arc_points(nx, my + 14, 16, 10, math.pi * 1.1, math.pi * 1.9, steps=10)
        rough_stroke(d, pts, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
    elif mouth_style == 'chew_open':
        pts = arc_points(nx, my + 4, 12, 10, 0, math.pi, steps=8)
        d.polygon(pts, fill=(170, 50, 65))
        rough_stroke(d, pts, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
        rough_stroke(d, line_points(nx - 12, my + 4, nx + 12, my + 4, steps=6), fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
    elif mouth_style == 'chew_closed':
        pts_l = arc_points(nx - 8, my, 8, 7, math.pi * 0.1, math.pi * 0.9, steps=6)
        pts_r = arc_points(nx + 8, my, 8, 7, math.pi * 0.1, math.pi * 0.9, steps=6)
        rough_stroke(d, pts_l, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)
        rough_stroke(d, pts_r, fill=LINE_COLOR, width=3, jitter=1.0, rng=rng)

    # 6. Thought Food (Hungry)
    if thought_food:
        bx, by = 195, 26
        rough_polygon(d, bx - 2, by + 18, 5, 5, fill=(255, 255, 255), outline=LINE_COLOR, pts=8, jitter=1.0, rng=rng)
        rough_polygon(d, bx + 8, by + 10, 7, 7, fill=(255, 255, 255), outline=LINE_COLOR, pts=8, jitter=1.0, rng=rng)
        rough_polygon(d, bx + 12, by - 6, 24, 18, fill=(255, 255, 255), outline=LINE_COLOR, pts=14, jitter=1.5, rng=rng)
        rough_polygon(d, bx + 6, by - 8, 9, 7, fill=(215, 120, 50), outline=LINE_COLOR, pts=8, jitter=1.0, rng=rng)
        rough_stroke(d, line_points(bx + 14, by - 8, bx + 22, by - 4, steps=4), fill=(240, 240, 240), width=4, jitter=0.8, rng=rng)

    # 7. Floating Zzz (Sleeping)
    if zzz_step >= 0:
        zy = 32 - (zzz_step * 5)
        d.text((185 + rng.randint(-1, 1), zy + 10 + rng.randint(-1, 1)), 'z', fill=(85, 115, 175))
        d.text((198 + rng.randint(-1, 1), zy + rng.randint(-1, 1)), 'Z', fill=(55, 85, 150))

    # 8. Soap Bubbles (Washing)
    if bubbles_step >= 0:
        for bx, by, r in [(25, 25 + bubbles_step * 3, 14), (205, 20 - bubbles_step * 3, 16), (28, 115, 10), (202, 110, 12)]:
            rough_polygon(d, bx + r//2, by + r//2, r//2, r//2, fill=(185, 225, 245), outline=(65, 160, 220), pts=10, jitter=1.2, rng=rng)
            d.point((bx + 3, by + 3), fill=(255, 255, 255))

    # 9. Bouncing Ball (Playing)
    if ball_step >= 0:
        ball_x = 200 + (ball_step * 4)
        ball_y = 100 - [0, 24, 38, 28, 14, 0][ball_step % 6]
        rough_polygon(d, ball_x, ball_y, 12, 12, fill=(240, 70, 60), outline=LINE_COLOR, pts=12, jitter=1.2, rng=rng)
        rough_stroke(d, arc_points(ball_x, ball_y, 8, 8, math.pi * 0.2, math.pi * 0.8, steps=6), fill=(255, 255, 255), width=2, jitter=0.6, rng=rng)

    # 10. Crumbs (Eating)
    if chew_crumb:
        rough_polygon(d, nx + 18, my + 8, 3, 3, fill=(215, 130, 60), pts=6, jitter=0.8, rng=rng)
        rough_polygon(d, nx - 20, my + 10, 3, 3, fill=(215, 130, 60), pts=6, jitter=0.8, rng=rng)

    return im

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(HEADER_PATH), exist_ok=True)

    anims = {
        # Idle: line-boiling alive in place at ~120ms with a quick natural blink!
        'idle': ([
            draw_wiggly_frame(101, eye_style='idle', mouth_style='cat', y_off=0),
            draw_wiggly_frame(102, eye_style='idle', mouth_style='cat', y_off=0),
            draw_wiggly_frame(103, eye_style='idle', mouth_style='cat', y_off=0),
            draw_wiggly_frame(104, eye_style='idle', mouth_style='cat', y_off=0),
            draw_wiggly_frame(105, eye_style='blink', mouth_style='cat', y_off=0),
            draw_wiggly_frame(106, eye_style='idle', mouth_style='cat', y_off=0),
        ], [130, 130, 130, 130, 100, 130]),

        # Happy: boiling ^ ^ eyes, open smile with tooth, gentle bounce & blush
        'happy': ([
            draw_wiggly_frame(201, eye_style='happy', mouth_style='open_cat', blush=True, y_off=0),
            draw_wiggly_frame(202, eye_style='happy', mouth_style='open_cat', blush=True, y_off=-2),
            draw_wiggly_frame(203, eye_style='happy', mouth_style='open_cat', blush=True, y_off=0),
            draw_wiggly_frame(204, eye_style='happy', mouth_style='cat', blush=True, y_off=1),
        ], [160, 160, 160, 160]),

        # Hungry: sad droopy eyes, shiver, thought bubble with food
        'hungry': ([
            draw_wiggly_frame(301, eye_style='sad', mouth_style='sad', thought_food=True, x_off=0, y_off=0),
            draw_wiggly_frame(302, eye_style='sad', mouth_style='sad', thought_food=True, x_off=-1, y_off=1),
            draw_wiggly_frame(303, eye_style='sad', mouth_style='sad', thought_food=True, x_off=0, y_off=0),
            draw_wiggly_frame(304, eye_style='sad', mouth_style='sad', thought_food=True, x_off=1, y_off=1),
        ], [180, 180, 180, 180]),

        # Dirty: cute silly face with wiggling tongue :P and dirt smudges
        'dirty': ([
            draw_wiggly_frame(401, eye_style='idle', mouth_style='tongue', dirt=True, y_off=0),
            draw_wiggly_frame(402, eye_style='idle', mouth_style='tongue', dirt=True, y_off=0),
            draw_wiggly_frame(403, eye_style='blink', mouth_style='tongue', dirt=True, y_off=0),
            draw_wiggly_frame(404, eye_style='idle', mouth_style='tongue', dirt=True, y_off=0),
        ], [200, 200, 120, 200]),

        # Eating: munching cycle with crumbs
        'eating': ([
            draw_wiggly_frame(501, eye_style='idle', mouth_style='chew_open', blush=True, y_off=0),
            draw_wiggly_frame(502, eye_style='happy', mouth_style='chew_closed', blush=True, chew_crumb=True, y_off=1),
            draw_wiggly_frame(503, eye_style='idle', mouth_style='chew_open', blush=True, y_off=0),
            draw_wiggly_frame(504, eye_style='happy', mouth_style='chew_closed', blush=True, chew_crumb=True, y_off=1),
        ], [160, 160, 160, 160]),

        # Washing: cheerful boiling smile and drifting soap bubbles
        'washing': ([
            draw_wiggly_frame(601, eye_style='happy', mouth_style='open_cat', blush=True, bubbles_step=0),
            draw_wiggly_frame(602, eye_style='happy', mouth_style='open_cat', blush=True, bubbles_step=1),
            draw_wiggly_frame(603, eye_style='happy', mouth_style='cat', blush=True, bubbles_step=2),
            draw_wiggly_frame(604, eye_style='happy', mouth_style='open_cat', blush=True, bubbles_step=3),
        ], [160, 160, 160, 160]),

        # Sleeping: peaceful u u eyes, gentle breathing and floating Zzz
        'sleeping': ([
            draw_wiggly_frame(701, eye_style='sleep', mouth_style='cat', zzz_step=0, y_off=0),
            draw_wiggly_frame(702, eye_style='sleep', mouth_style='cat', zzz_step=1, y_off=1),
            draw_wiggly_frame(703, eye_style='sleep', mouth_style='cat', zzz_step=2, y_off=2),
            draw_wiggly_frame(704, eye_style='sleep', mouth_style='cat', zzz_step=3, y_off=1),
        ], [250, 250, 250, 250]),

        # Playing: playful wink and bouncing ball
        'playing': ([
            draw_wiggly_frame(801, eye_style='wink', mouth_style='open_cat', ball_step=0, y_off=0),
            draw_wiggly_frame(802, eye_style='idle', mouth_style='open_cat', ball_step=1, y_off=-2),
            draw_wiggly_frame(803, eye_style='happy', mouth_style='open_cat', ball_step=2, y_off=-1),
            draw_wiggly_frame(804, eye_style='wink', mouth_style='cat', ball_step=3, y_off=0),
            draw_wiggly_frame(805, eye_style='idle', mouth_style='open_cat', ball_step=4, y_off=-1),
            draw_wiggly_frame(806, eye_style='happy', mouth_style='cat', ball_step=5, y_off=0),
        ], [130, 130, 130, 130, 130, 130]),
    }

    header_content = """// Auto-generated Wiggly Paint pet animations header for ESP32 Tamagotchi
// Authentic hand-drawn line boiling aesthetic with living vibrating strokes
#pragma once
#include <Arduino.h>

"""
    tot_bytes = 0
    for name, (frames, durations) in anims.items():
        pal = frames[0].convert('P', palette=Image.ADAPTIVE, colors=32)
        q_frames = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
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
