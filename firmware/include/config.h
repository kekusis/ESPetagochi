#pragma once
#include <Arduino.h>

// ==========================================
// Display Configuration (Waveshare ESP32-S3-LCD-1.3)
// ==========================================
#define LCD_WIDTH    240
#define LCD_HEIGHT   240

#define TFT_DC       38
#define TFT_CS       39
#define TFT_SCK      40
#define TFT_MOSI     41
#define TFT_RST      42
#define TFT_BL       -1  // Set to -1 if backlight is always on, or GPIO if controlled

// Full-screen Pet GIF Coordinates (240x152 GIF: stretched across the entire display!)
#define PET_GIF_W    240
#define PET_GIF_H    152
#define PET_GIF_X    0                               // Touches left and right screen borders!
#define PET_GIF_Y    44                              // Below status bar (Y: 44 to 196)

// ==========================================
// Hardware Button Pins (Configurable)
// Active LOW (internal pullups enabled)
// ==========================================
#define PIN_BTN_FEED   14  // Button 1: Feed / Snack Minigame (Lane 1)
#define PIN_BTN_WASH   13  // Button 2: Wash / Bubble Scrub Minigame (Lane 2)
#define PIN_BTN_PLAY   12  // Button 3: Play / Reaction Minigame (Lane 3)
#define PIN_BTN_SLEEP  11  // Button 4: Sleep / Lights / Menu Toggle (Lane 4)

// Debounce time in milliseconds
#define BTN_DEBOUNCE_MS 50

// ==========================================
// Buzzer / Piezo Audio Configuration
// Passive piezo buzzer on PWM pin (set to -1 to disable hardware output)
// ==========================================
#define PIN_BUZZER    5   // Configurable GPIO pin for passive piezo buzzer

// ==========================================
// Pet Mechanics Configuration
// ==========================================
#define HUNGER_MAX       100
#define CLEANLINESS_MAX  100
#define HAPPINESS_MAX    100
#define ENERGY_MAX       100

// Rate of stat decay (milliseconds per 1 point decrease)
#define HUNGER_DECAY_INTERVAL_MS      15000  // -1 every 15s
#define CLEAN_DECAY_INTERVAL_MS       25000  // -1 every 25s
#define ENERGY_DECAY_INTERVAL_MS      30000  // -1 every 30s
#define ENERGY_REGEN_INTERVAL_MS      4000   // +1 every 4s when sleeping

// Random idle animation interval (ms) - idle plays frequently
#define IDLE_ACTION_MIN_MS  18000
#define IDLE_ACTION_MAX_MS  40000
