# 🎮 ESP32 Tamagotchi Quickstart & Guide

Your ESP32 is flashed and running the Tamagotchi firmware!

---

## 🕹️ Controls (Physical & PC Remote)

Because your 4 physical buttons are not yet wired to the ESP, **you can control everything directly from your PC!**

### Option A: The PC GUI Controller (Recommended)
Launch the graphical test controller with 4 big buttons and a live serial feed:
```powershell
python "C:\Users\pezda\Desktop\ESPetagochi-main\tools\pc_controller.py"
```
You can click the on-screen buttons or simply press keys **`1`**, **`2`**, **`3`**, **`4`** on your keyboard while the window is focused.

### Option B: Terminal / Serial Monitor
Open any serial monitor (or run `python tools/pc_controller.py --cli`) on **`COM7`** at **`115200 baud`**:
- Send **`1`** (or `feed`): Button 1 (Feed / Snack Catch)
- Send **`2`** (or `wash`): Button 2 (Wash / Bubble Scrub)
- Send **`3`** (or `play`): Button 3 (Play / Reaction Game)
- Send **`4`** (or `sleep`): Button 4 (Sleep / Wake Toggle)
- Send **`status`**: Print pet stats & mood
- Send **`set hunger 10`**, **`set clean 10`**, etc. to test different emotion reactions!

---

## 📌 Hardware Pinout (When Connecting Physical Buttons)

All buttons are configured with internal pullups (`INPUT_PULLUP`). Connect one side of each button to the GPIO pin and the other side to `GND`:

| Button | Function | Default Pin | Behavior |
|---|---|---|---|
| **Button 1** | **Feed** | `GPIO 1` | Launches snack catch timing game |
| **Button 2** | **Wash** | `GPIO 2` | Launches bubble scrub cleaning game |
| **Button 3** | **Play** | `GPIO 3` | Launches dodge/reaction match game |
| **Button 4** | **Sleep / Wake** | `GPIO 4` | Puts pet to sleep to regenerate energy |

> You can change any of these pins anytime in [`firmware/include/config.h`](file:///C:/Users/pezda/Desktop/ESPetagochi-main/firmware/include/config.h).

---

## 👾 Included Minigames

1. **Feeding ("Falling Treats Catcher"):**
   - Treats (Apples, Cookies, Berries) fall randomly from the top across **4 lanes**!
   - Your pet stays on screen at the bottom. Press **[1]**, **[2]**, **[3]**, or **[4]** to move your pet into that lane to catch the snack!
   - When caught, the pet chomps ("NOM!"), plays the eating animation, and replenishes Hunger and Happiness.
   - 6 treats per game session.

2. **Washing ("Bubble Scrub"):**
   - The pet remains visible in the center while covered in 4 soap bubbles labeled **1, 2, 3, 4**.
   - Press the corresponding button to pop each bubble off the pet.
   - When all 4 are popped, pet plays the `washing.gif` bath animation and restores Cleanliness to 100%.

3. **Playing ("Dodge & Match"):**
   - The pet is visible in the center! The pet signals Left (Button 1) or Right (Button 2).
   - Match the direction before the timer expires to win!
   - Pet plays the `playing.gif` ball-bounce animation and boosts Happiness.

---

## 🎨 How to Replace the Placeholder GIFs

All current placeholder GIFs are located in:
👉 [`assets/gifs/`](file:///C:/Users/pezda/Desktop/ESPetagochi-main/assets/gifs/)

The animations currently used are:
- `idle.gif`: Normal gentle breathing and blinking
- `happy.gif`: Excited jumping with hearts/sparkles
- `hungry.gif`: Tummy grumbling, thought bubble of food
- `dirty.gif`: Mud spots, stink lines
- `eating.gif`: Chewing food with crumbs
- `washing.gif`: Bathtub with floating bubbles
- `sleeping.gif`: Curled up with nightcap & animated "Zzz"
- `playing.gif`: Bouncing ball

### Steps to Replace:
1. Export your custom GIF (recommended: **128x128 pixels**, 256 colors or less).
2. Save it into `assets/gifs/` with the exact corresponding filename (e.g., `idle.gif`).
3. Run the conversion script:
   ```powershell
   python "C:\Users\pezda\Desktop\ESPetagochi-main\tools\convert_custom_gifs.py"
   ```
4. Re-upload the firmware:
   ```powershell
   cd "C:\Users\pezda\Desktop\ESPetagochi-main\firmware"
   python -m platformio run --target upload
   ```
