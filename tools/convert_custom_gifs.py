"""
Utility script to convert GIF files from assets/gifs/*.gif into pet_gifs.h
Usage: python tools/convert_custom_gifs.py
Drop your own idle.gif, happy.gif, hungry.gif, dirty.gif, eating.gif, washing.gif, sleeping.gif, playing.gif
into assets/gifs/ and run this script!
"""
import os

GIFS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "gifs"))
HEADER_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "firmware", "include", "pet_gifs.h"))

ANIM_NAMES = ["idle", "happy", "hungry", "dirty", "eating", "washing", "sleeping", "playing"]

def main():
    if not os.path.exists(GIFS_DIR):
        print(f"Error: {GIFS_DIR} does not exist!")
        return

    header_content = """// Auto-generated pet animations header for ESP32 Tamagotchi
// Replace GIF files in assets/gifs/ and run tools/convert_custom_gifs.py
#pragma once
#include <Arduino.h>

"""
    found = 0
    for name in ANIM_NAMES:
        path = os.path.join(GIFS_DIR, f"{name}.gif")
        if not os.path.exists(path):
            print(f"Warning: {name}.gif not found in {GIFS_DIR}")
            continue

        with open(path, "rb") as f:
            data = f.read()

        found += 1
        print(f"Packing {name}.gif ({len(data)} bytes)...")
        header_content += f"// {name}.gif ({len(data)} bytes)\n"
        header_content += f"const uint8_t gif_{name}[] PROGMEM = {{\n  "
        hex_vals = [f"0x{b:02X}" for b in data]
        for i in range(0, len(hex_vals), 16):
            header_content += ", ".join(hex_vals[i:i+16]) + (",\n  " if i+16 < len(hex_vals) else "\n};\n")
        header_content += f"const size_t gif_{name}_len = sizeof(gif_{name});\n\n"

    with open(HEADER_PATH, "w") as f:
        f.write(header_content)

    print(f"Successfully wrote {found} animations to {HEADER_PATH}")

if __name__ == "__main__":
    main()
