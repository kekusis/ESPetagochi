#include <Arduino.h>
#include <Arduino_GFX_Library.h>
#include <AnimatedGIF.h>
#include <Preferences.h>
#include <time.h>
#include <sys/time.h>

#include "config.h"
#include "pet_gifs.h"
#include "PetState.h"

// ==========================================
// Hardware & Display Objects
// ==========================================
Arduino_DataBus *bus = new Arduino_ESP32SPI(
    TFT_DC, TFT_CS, TFT_SCK, TFT_MOSI, GFX_NOT_DEFINED
);

Arduino_GFX *gfx = new Arduino_ST7789(
    bus, TFT_RST, 0 /* rotation */, true /* IPS */, LCD_WIDTH, LCD_HEIGHT
);

AnimatedGIF gif;
Pet pet;
Preferences prefs;
AppMode currentMode = MODE_PET;

// Dynamic Pet Placement (allows pet to move across lanes in minigames!)
int petDrawX = PET_GIF_X;
int petDrawY = PET_GIF_Y;

// Animation playback state
PetEmotion activeGifEmotion = (PetEmotion)-1;
unsigned long nextFrameTime = 0;
bool gifLoaded = false;

// Time tracking & Persistence
bool timeSynchronized = false;
unsigned long lastSaveTime = 0;
#define SAVE_INTERVAL_MS 30000 // Auto-save to NVS every 30s

// Color Definitions (RGB565)
#define COLOR_PET_BG      0x9CD3  // Darker gray fur (RGB: 155, 155, 155 - exact match to GIF background)
#define COLOR_BG          0x18E4  // Dark slate for HUD panels & toolbars
#define COLOR_WHITE       0xFFFF
#define COLOR_BLACK       0x0000
#define COLOR_GRAY        0x7BEF
#define COLOR_DARK_GRAY   0x31A6
#define COLOR_HUNGER      0xFD00  // Orange/Gold
#define COLOR_CLEAN       0x5EBF  // Aqua/Cyan
#define COLOR_HAPPY       0xFA08  // Coral/Pink
#define COLOR_ENERGY      0xFFE0  // Yellow
#define COLOR_BAR_BG      0x2124  // Bar slot background
#define COLOR_BORDER      0x4A69  // Retro border
#define COLOR_ACCENT      0x07E0  // Bright green
#define COLOR_RED         0xF800  // Red for apples

// Physical Button Debounce tracking
struct Button {
    uint8_t pin;
    bool lastState;
    bool currentState;
    unsigned long lastDebounceTime;
};

Button buttons[4] = {
    {PIN_BTN_FEED, HIGH, HIGH, 0},
    {PIN_BTN_WASH, HIGH, HIGH, 0},
    {PIN_BTN_PLAY, HIGH, HIGH, 0},
    {PIN_BTN_SLEEP, HIGH, HIGH, 0}
};

// ==========================================
// Minigame Variables
// ==========================================
// 4 Lanes for Food Catch Minigame
const int laneX[4] = {34, 91, 149, 206};
int petLane = 1; // Pet starts in lane 1 (0 to 3)
int lastTreatLane = -1; // Guaranteed variety tracker!

struct FallingTreat {
    bool active;
    int lane;
    int x;
    int y;
    int prevY;
    int type; // 0=Apple, 1=Cookie, 2=Berry
    int speed;
};

FallingTreat currentTreat;
int feedTreatsTotal = 8;
int feedTreatsSpawned = 0;
int feedScore = 0;
unsigned long nextTreatSpawnTime = 0;

// Wash Game (Bubble Scrub)
const int bubbleCenterX[4] = {30, 210, 36, 204};
const int bubbleCenterY[4] = {65, 65, 142, 142};
const int bubbleRadius = 18;
bool washBubbles[4] = {true, true, true, true};
int washBubblesLeft = 4;

// Play Game (Direction Match)
int playTargetDir = 0; // 0 = Left (Btn 1), 1 = Right (Btn 2)
int playRoundsLeft = 0;
int playScore = 0;
unsigned long playRoundStartTime = 0;
bool playHappyMoment = false;
unsigned long playHappyUntil = 0;
unsigned long playNextRoundTime = 0;

// ==========================================
// Forward Declarations
// ==========================================
void handleButtonPress(int btnIndex);
void loadPetGif(PetEmotion emotion);
void drawPetScreen(bool fullRedraw = false);
void drawStatusBar();
void drawFooter();
void printSerialHelp();
void printPetStatusSerial();
void savePetState();
void loadPetState();

// Minigame functions
void startFeedGame();
void updateFeedGame();
void handleFeedGameInput(int btnIndex);
void drawFeedScore();
void drawTreat(int x, int y, int type);
void eraseTreat(int x, int y);

void startWashGame();
void updateWashGame();
void handleWashGameInput(int btnIndex);
void drawWashScore();
void drawWashBubbles();

void startPlayGame();
void updatePlayGame();
void handlePlayGameInput(int btnIndex);

// ==========================================
// GIFDraw Callback for AnimatedGIF
// ==========================================
void GIFDraw(GIFDRAW *pDraw) {
    uint8_t *s = pDraw->pPixels;
    uint16_t *palette = pDraw->pPalette;
    int y = petDrawY + pDraw->iY + pDraw->y;
    int x = petDrawX + pDraw->iX;
    int w = pDraw->iWidth;

    // Handle left-side clipping cleanly
    if (x < 0) {
        int skip = -x;
        if (skip >= w) return;
        s += skip;
        w -= skip;
        x = 0;
    }

    // Handle right-side clipping
    if (x + w > LCD_WIDTH) {
        w = LCD_WIDTH - x;
    }
    if (y < 0 || y >= LCD_HEIGHT || w <= 0) return;

    static uint16_t lineBuf[LCD_WIDTH];
    
    // In wash minigame, calculate active bubble exclusion spans for this scanline 'y'
    // By skipping bubble pixels during GIF rendering, the bubbles never get erased and NEVER flicker!
    bool hasBubbleExcl = false;
    int exclX1[4], exclX2[4], numExcl = 0;
    if (currentMode == MODE_GAME_WASH) {
        for (int b = 0; b < 4; b++) {
            if (washBubbles[b]) {
                int dy = abs(y - bubbleCenterY[b]);
                if (dy <= bubbleRadius) {
                    int dx = sqrt(bubbleRadius * bubbleRadius - dy * dy);
                    exclX1[numExcl] = bubbleCenterX[b] - dx;
                    exclX2[numExcl] = bubbleCenterX[b] + dx;
                    numExcl++;
                    hasBubbleExcl = true;
                }
            }
        }
    }

    // In play minigame, calculate active arrow exclusion so arrows always stay on top of face (zero Z-fight!)
    bool hasArrowExcl = false;
    int arrowX1 = 0, arrowX2 = 0;
    if (currentMode == MODE_GAME_PLAY && !playHappyMoment) {
        if (y >= 84 && y <= 132) {
            if (playTargetDir == 0) {
                arrowX1 = 6; arrowX2 = 54;
                hasArrowExcl = true;
            } else {
                arrowX1 = 186; arrowX2 = 234;
                hasArrowExcl = true;
            }
        }
    }

    int spanStart = -1;
    int spanLen = 0;
    uint8_t trans = pDraw->ucHasTransparency ? pDraw->ucTransparent : 255;
    bool checkTrans = pDraw->ucHasTransparency;

    for (int i = 0; i < w; i++) {
        uint8_t pixel = s[i];
        int px = x + i;
        bool skip = (checkTrans && pixel == trans);
        if (!skip && hasBubbleExcl) {
            for (int b = 0; b < numExcl; b++) {
                if (px >= exclX1[b] && px <= exclX2[b]) {
                    skip = true;
                    break;
                }
            }
        }
        if (!skip && hasArrowExcl) {
            if (px >= arrowX1 && px <= arrowX2) {
                skip = true;
            }
        }

        if (!skip) {
            if (spanStart == -1) {
                spanStart = i;
                spanLen = 0;
            }
            lineBuf[spanLen++] = palette[pixel];
        } else {
            if (spanStart != -1) {
                gfx->draw16bitRGBBitmap(x + spanStart, y, lineBuf, spanLen, 1);
                spanStart = -1;
            }
        }
    }
    if (spanStart != -1) {
        gfx->draw16bitRGBBitmap(x + spanStart, y, lineBuf, spanLen, 1);
    }
}

// ==========================================
// GIF Management
// ==========================================
void loadPetGif(PetEmotion emotion) {
    const uint8_t *data = nullptr;
    size_t len = 0;

    switch (emotion) {
        case EMOTION_HAPPY:
            data = gif_happy; len = gif_happy_len; break;
        case EMOTION_HUNGRY:
            data = gif_hungry; len = gif_hungry_len; break;
        case EMOTION_DIRTY:
            data = gif_dirty; len = gif_dirty_len; break;
        case EMOTION_EATING:
            data = gif_eating; len = gif_eating_len; break;
        case EMOTION_WASHING:
            data = gif_washing; len = gif_washing_len; break;
        case EMOTION_SLEEPING:
            data = gif_sleeping; len = gif_sleeping_len; break;
        case EMOTION_PLAYING:
            data = gif_playing; len = gif_playing_len; break;
        case EMOTION_PLAY_LEFT:
            data = gif_play_left; len = gif_play_left_len; break;
        case EMOTION_PLAY_RIGHT:
            data = gif_play_right; len = gif_play_right_len; break;
        case EMOTION_IDLE:
        default:
            data = gif_idle; len = gif_idle_len; break;
    }

    if (gifLoaded) {
        gif.close();
        gifLoaded = false;
    }

    if (data && len > 0) {
        if (gif.open((uint8_t *)data, len, GIFDraw)) {
            gifLoaded = true;
            activeGifEmotion = emotion;
            nextFrameTime = millis();
        }
    }
}

// ==========================================
// Persistence (NVS) & Time Tracking
// ==========================================
void savePetState() {
    prefs.begin("kekusis", false);
    prefs.putInt("hunger", pet.hunger);
    prefs.putInt("clean", pet.cleanliness);
    prefs.putInt("happy", pet.happiness);
    prefs.putInt("energy", pet.energy);
    prefs.putBool("sleep", pet.isSleeping);
    
    time_t nowSec = time(nullptr);
    if (nowSec > 100000) {
        prefs.putULong("last_time", (unsigned long)nowSec);
    }
    prefs.end();
}

void loadPetState() {
    prefs.begin("kekusis", false);
    pet.hunger = prefs.getInt("hunger", 85);
    pet.cleanliness = prefs.getInt("clean", 90);
    pet.happiness = prefs.getInt("happy", 85);
    pet.energy = prefs.getInt("energy", 95);
    pet.isSleeping = prefs.getBool("sleep", false);
    unsigned long lastSavedEpoch = prefs.getULong("last_time", 0);
    prefs.end();

    Serial.printf("[NVS] Loaded Kekusis: H:%d%% C:%d%% P:%d%% E:%d%% (Last Saved: %lu)\n",
                  pet.hunger, pet.cleanliness, pet.happiness, pet.energy, lastSavedEpoch);
}

// ==========================================
// Drawing Functions (Large, Readable Text)
// ==========================================
void drawLargeMeter(int x, int y, int w, int h, int val, uint16_t color, const char *letter) {
    // Large 12x16 label in TextSize 2
    gfx->setTextColor(color);
    gfx->setTextSize(2);
    gfx->setCursor(x, y - 2);
    gfx->print(letter);

    // Thick colored meter bar
    int barX = x + 16;
    int barW = w - 16;
    gfx->drawRect(barX, y + 1, barW, h, COLOR_BORDER);
    gfx->fillRect(barX + 1, y + 2, barW - 2, h - 2, COLOR_BAR_BG);
    
    int fillW = (val * (barW - 2)) / 100;
    if (fillW > 0) {
        gfx->fillRect(barX + 1, y + 2, fillW, h - 2, color);
    }
}

void drawStatusBar() {
    // Header stats area on fur background (Y: 0 to 40) - seamless, no split line!
    gfx->fillRect(0, 0, LCD_WIDTH, 40, COLOR_PET_BG);

    // Row 1 (Y: 4): Hunger (H) & Cleanliness (C)
    drawLargeMeter(4, 4, 112, 12, pet.hunger, COLOR_HUNGER, "H");
    drawLargeMeter(124, 4, 112, 12, pet.cleanliness, COLOR_CLEAN, "C");

    // Row 2 (Y: 22): Happiness (P) & Energy (E)
    drawLargeMeter(4, 22, 112, 12, pet.happiness, COLOR_HAPPY, "P");
    drawLargeMeter(124, 22, 112, 12, pet.energy, COLOR_ENERGY, "E");
}

void drawFooter() {
    // Footer toolbar on fur background (Y: 200 to 240) - seamless, no split line!
    gfx->fillRect(0, 200, LCD_WIDTH, 40, COLOR_PET_BG);

    if (currentMode == MODE_PET) {
        const char *btnNums[4] = {"1", "2", "3", "4"};
        const char *btnLabels[4] = {"FEED", "WASH", "PLAY", pet.isSleeping ? "WAKE" : "ZZZ"};
        uint16_t btnColors[4] = {COLOR_HUNGER, COLOR_CLEAN, COLOR_HAPPY, COLOR_ENERGY};

        for (int i = 0; i < 4; i++) {
            int bx = 6 + i * 59;
            
            // Bold colored number (16px high: Y: 214 to 230 -> exactly 10px from bottom 240!)
            gfx->setTextColor(btnColors[i]);
            gfx->setTextSize(2);
            gfx->setCursor(bx, 214);
            gfx->print(btnNums[i]);

            // Clean action label in crisp dark text on fur background (8px high: Y: 222 to 230)
            gfx->setTextColor(COLOR_BLACK);
            gfx->setTextSize(1);
            gfx->setCursor(bx + 14, 222);
            gfx->print(btnLabels[i]);
        }
    }
}

void drawSpeechBubble() {
    // Y: 192 to 196 (just below pet GIF, above footer)
    gfx->fillRect(4, 192, LCD_WIDTH - 8, 5, COLOR_PET_BG);
    if (millis() < pet.statusMsgEndTime && strlen(pet.statusMsg) > 0) {
        // Overlay speech text on the bottom of the pet area
        int len = strlen(pet.statusMsg);
        if (len <= 16) {
            gfx->setTextColor(COLOR_BLACK);
            gfx->setTextSize(1);
            int textW = len * 6;
            int tx = max(12, (LCD_WIDTH - textW) / 2);
            gfx->setCursor(tx, 192);
            gfx->print(pet.statusMsg);
        } else {
            gfx->setTextColor(COLOR_BLACK);
            gfx->setTextSize(1);
            int textW = len * 6;
            int tx = max(12, (LCD_WIDTH - textW) / 2);
            gfx->setCursor(tx, 192);
            gfx->print(pet.statusMsg);
        }
    }
}

void drawPetScreen(bool fullRedraw) {
    if (fullRedraw) {
        petDrawX = PET_GIF_X;
        petDrawY = PET_GIF_Y;
        gfx->fillScreen(COLOR_PET_BG); // Light gray fur background!
        drawStatusBar();
        drawFooter();
    }
    drawSpeechBubble();
}

// ==========================================
// Treat Rendering for Food Minigame
// ==========================================
void drawFeedScore() {
    // Dedicated header banner at Y: 0 to 36 (completely above falling treats!)
    gfx->fillRect(0, 0, LCD_WIDTH, 36, COLOR_BG);
    gfx->drawFastHLine(0, 36, LCD_WIDTH, COLOR_BORDER);
    gfx->setTextColor(COLOR_HUNGER);
    gfx->setTextSize(2);
    // Center "SCORE: X / 8" (144px width in 240px screen)
    gfx->setCursor(48, 10);
    gfx->printf("SCORE: %d / %d", feedScore, feedTreatsTotal);
}

void drawTreat(int x, int y, int type) {
    if (y < 42) return; // Never render over the header boundary
    if (type == 0) {
        // Red Apple
        gfx->fillCircle(x, y, 7, COLOR_RED);
        gfx->drawFastVLine(x, y - 8, 3, 0x8A22); // Brown stem
        gfx->drawPixel(x + 1, y - 7, COLOR_ACCENT); // Green leaf
    } else if (type == 1) {
        // Golden Cookie
        gfx->fillCircle(x, y, 7, 0xFEA0);
        gfx->drawPixel(x - 2, y - 1, 0x6180);
        gfx->drawPixel(x + 2, y + 1, 0x6180);
        gfx->drawPixel(x, y + 2, 0x6180);
    } else {
        // Strawberry
        gfx->fillTriangle(x - 6, y - 3, x + 6, y - 3, x, y + 7, 0xF948);
        gfx->drawFastHLine(x - 3, y - 4, 7, COLOR_ACCENT);
    }
}

void eraseTreat(int x, int y) {
    // Strictly erase between the header boundary (Y > 36) and down to screen bottom
    // Erases with COLOR_PET_BG (fur color) so food moves cleanly across the fur!
    int top = max(37, y - 9);
    int bottom = min(LCD_HEIGHT, y + 10);
    if (bottom > top) {
        gfx->fillRect(x - 9, top, 19, bottom - top, COLOR_PET_BG);
    }
}

// ==========================================
// Minigame 1: FALLING TREATS (Smooth, Non-lagging, Non-repeating lanes)
// ==========================================
void startFeedGame() {
    currentMode = MODE_GAME_FEED;
    feedTreatsTotal = 8;
    feedTreatsSpawned = 0;
    feedScore = 0;
    petLane = 1;
    lastTreatLane = -1;

    // Position pet at bottom of screen
    petDrawX = laneX[petLane] - (PET_GIF_W / 2);
    petDrawY = 88;

    currentTreat.active = false;
    nextTreatSpawnTime = millis() + 300;

    gfx->fillScreen(COLOR_PET_BG); // Fur background!

    // Dedicated banner (Y: 0 to 36)
    drawFeedScore();

    loadPetGif(EMOTION_IDLE);
    gif.playFrame(true, NULL);

    Serial.println("\n>>> MINIGAME: FAST FALLING TREATS STARTED <<<");
    Serial.println("Treats falling! Press [1], [2], [3], [4] on keyboard to catch them!");
}

void updateFeedGame() {
    unsigned long now = millis();

    // 1. Keep Pet GIF playing at its current lane position FIRST
    if (gifLoaded && now >= nextFrameTime) {
        int iDelay = 0;
        if (!gif.playFrame(true, &iDelay)) {
            loadPetGif(pet.overrideEndTime > now ? pet.overrideEmotion : EMOTION_IDLE);
        } else {
            nextFrameTime = now + iDelay;
        }
    }

    // 2. Spawn a new treat with guaranteed variety
    if (!currentTreat.active && feedTreatsSpawned < feedTreatsTotal) {
        if (now >= nextTreatSpawnTime) {
            currentTreat.active = true;

            int offset = 1 + random(3);
            currentTreat.lane = (lastTreatLane == -1) ? random(4) : (lastTreatLane + offset) % 4;
            lastTreatLane = currentTreat.lane;

            currentTreat.x = laneX[currentTreat.lane];
            currentTreat.y = 44;
            currentTreat.prevY = 44;
            currentTreat.type = random(3);
            // Steady, smooth fall speed (no sudden jump or lag)
            currentTreat.speed = 8 + (feedTreatsSpawned * 3 / 4);
            feedTreatsSpawned++;
            Serial.printf("-> Treat #%d falling in Lane %d! (Speed: %d)\n", feedTreatsSpawned, currentTreat.lane + 1, currentTreat.speed);
        }
    }

    // 3. Animate falling treat ON TOP of pet so it never lags or gets overwritten
    if (currentTreat.active) {
        eraseTreat(currentTreat.x, currentTreat.prevY);
        currentTreat.prevY = currentTreat.y;
        currentTreat.y += currentTreat.speed;

        // Catch window: Y = 135 to 165
        if (currentTreat.y >= 135 && currentTreat.y <= 165) {
            if (currentTreat.lane == petLane) {
                // CAUGHT!
                eraseTreat(currentTreat.x, currentTreat.y);
                currentTreat.active = false;
                feedScore++;
                pet.hunger = min(HUNGER_MAX, pet.hunger + 14);
                pet.happiness = min(HAPPINESS_MAX, pet.happiness + 8);

                drawFeedScore();

                loadPetGif(EMOTION_EATING);
                pet.triggerEmotionOverride(EMOTION_EATING, 700);
                gif.playFrame(true, NULL);

                Serial.printf("-> YUM! Caught in Lane %d! Score: %d/%d\n", petLane + 1, feedScore, feedTreatsTotal);
                nextTreatSpawnTime = now + 160;
            }
        }

        // Miss check
        if (currentTreat.active && currentTreat.y > 175) {
            eraseTreat(currentTreat.x, currentTreat.y);
            currentTreat.active = false;
            Serial.printf("-> MISSED in Lane %d!\n", currentTreat.lane + 1);
            nextTreatSpawnTime = now + 140;
        }

        if (currentTreat.active) {
            drawTreat(currentTreat.x, currentTreat.y, currentTreat.type);
        }
    }

    // 4. Check if game finished
    if (!currentTreat.active && feedTreatsSpawned >= feedTreatsTotal) {
        delay(400);
        currentMode = MODE_PET;
        petDrawX = PET_GIF_X;
        petDrawY = PET_GIF_Y;

        pet.triggerEmotionOverride(feedScore >= 4 ? EMOTION_HAPPY : EMOTION_IDLE, 3500);
        char summary[32];
        snprintf(summary, sizeof(summary), "Caught %d/%d! Yum!", feedScore, feedTreatsTotal);
        pet.setStatus(summary, 3000);

        drawPetScreen(true);
        loadPetGif(feedScore >= 4 ? EMOTION_HAPPY : EMOTION_IDLE);
        savePetState();
        printPetStatusSerial();
        return;
    }

    delay(10);
}

void handleFeedGameInput(int btnIndex) {
    if (btnIndex < 0 || btnIndex > 3) return;

    if (petLane != btnIndex) {
        // Clear previous pet area with light gray fur
        gfx->fillRect(0, petDrawY, LCD_WIDTH, PET_GIF_H, COLOR_PET_BG);

        petLane = btnIndex;
        petDrawX = laneX[petLane] - (PET_GIF_W / 2);

        // Immediately rewind and redraw full keyframe at new position to eliminate glitches!
        loadPetGif(pet.overrideEndTime > millis() ? pet.overrideEmotion : EMOTION_IDLE);
        gif.playFrame(true, NULL);

        Serial.printf("-> Kekusis moved to Lane %d!\n", petLane + 1);
    }
}

// ==========================================
// Minigame 2: BUBBLE SCRUB (Zero-Flicker Hardware Exclusion, Large Pet)
// ==========================================
void drawWashScore() {
    gfx->fillRect(0, 0, LCD_WIDTH, 36, COLOR_BG);
    gfx->drawFastHLine(0, 36, LCD_WIDTH, COLOR_BORDER);
    gfx->setTextColor(COLOR_CLEAN);
    gfx->setTextSize(2);
    // Center "BUBBLES: X / 4"
    gfx->setCursor(34, 10);
    gfx->printf("BUBBLES: %d / 4", washBubblesLeft);
}

void drawWashBubbles() {
    for (int i = 0; i < 4; i++) {
        if (washBubbles[i]) {
            int cx = bubbleCenterX[i];
            int cy = bubbleCenterY[i];
            int r = bubbleRadius;

            // Outer bubble rim
            gfx->drawCircle(cx, cy, r, COLOR_CLEAN);
            // Translucent soapy wash fill
            gfx->fillCircle(cx, cy, r - 2, 0x2A9C);
            // Bright white reflection glint
            gfx->fillCircle(cx - 5, cy - 5, 3, COLOR_WHITE);

            // Large bold button number in TextSize 2
            gfx->setTextColor(COLOR_WHITE);
            gfx->setTextSize(2);
            gfx->setCursor(cx - 5, cy - 7);
            gfx->printf("%d", i + 1);
        }
    }
}

void startWashGame() {
    currentMode = MODE_GAME_WASH;
    washBubblesLeft = 4;
    for (int i = 0; i < 4; i++) washBubbles[i] = true;

    petDrawX = PET_GIF_X;
    petDrawY = PET_GIF_Y;

    gfx->fillScreen(COLOR_PET_BG); // Light gray fur background!
    drawWashScore();

    loadPetGif(EMOTION_DIRTY);
    gif.playFrame(true, NULL);
    drawWashBubbles();

    Serial.println("\n>>> MINIGAME: WASHING STARTED <<<");
    Serial.println("Kekusis is covered in bubbles! Press [1], [2], [3], [4] to scrub all spots off!");
}

void updateWashGame() {
    unsigned long now = millis();

    // 1. Keep Pet GIF playing in the center!
    // GIFDraw automatically skips active bubble regions so they NEVER flicker!
    if (gifLoaded && now >= nextFrameTime) {
        int iDelay = 0;
        if (!gif.playFrame(true, &iDelay)) {
            loadPetGif(EMOTION_DIRTY);
        } else {
            nextFrameTime = now + iDelay;
        }
    }

    delay(10);
}

void handleWashGameInput(int btnIndex) {
    if (btnIndex >= 0 && btnIndex < 4) {
        if (washBubbles[btnIndex]) {
            washBubbles[btnIndex] = false;
            washBubblesLeft--;

            // Pop effect
            int cx = bubbleCenterX[btnIndex];
            int cy = bubbleCenterY[btnIndex];
            int r = bubbleRadius;

            // Flash expanding pop ring
            gfx->drawCircle(cx, cy, r + 4, COLOR_WHITE);
            delay(50);
            gfx->drawCircle(cx, cy, r + 4, COLOR_PET_BG);

            // Re-render current frame so the popped bubble area is restored to pet skin
            gif.playFrame(true, NULL);
            drawWashBubbles();

            // Update header
            drawWashScore();

            Serial.printf("-> POPPED Bubble %d! (%d remaining)\n", btnIndex + 1, washBubblesLeft);
        }
    }

    if (washBubblesLeft <= 0) {
        pet.cleanliness = min(CLEANLINESS_MAX, pet.cleanliness + 50);
        pet.happiness = min(HAPPINESS_MAX, pet.happiness + 20);
        currentMode = MODE_PET;
        petDrawX = PET_GIF_X;
        petDrawY = PET_GIF_Y;

        pet.triggerEmotionOverride(EMOTION_WASHING, 4000);
        pet.setStatus("Squeaky clean!", 3500);
        drawPetScreen(true);
        loadPetGif(EMOTION_WASHING);
        savePetState();
        printPetStatusSerial();
    }
}

// ==========================================
// Minigame 3: DODGE & PLAY (Direction Match)
// ==========================================
void startPlayGame() {
    currentMode = MODE_GAME_PLAY;
    playRoundsLeft = 3;
    playScore = 0;
    playTargetDir = random(2);
    playRoundStartTime = millis();
    playHappyMoment = false;
    playHappyUntil = 0;
    playNextRoundTime = 0;

    petDrawX = 0; // Centered (not moved horizontally)
    petDrawY = PET_GIF_Y;

    gfx->fillScreen(COLOR_PET_BG); // Fur background

    // Large Header
    gfx->fillRect(0, 0, LCD_WIDTH, 36, COLOR_BG);
    gfx->drawFastHLine(0, 36, LCD_WIDTH, COLOR_BORDER);
    gfx->setTextColor(COLOR_HAPPY);
    gfx->setTextSize(2);
    gfx->setCursor(24, 10);
    gfx->print("MATCH KEKUSIS!");

    // Load authentic 20-degree rotated face matching direction
    loadPetGif(playTargetDir == 0 ? EMOTION_PLAY_LEFT : EMOTION_PLAY_RIGHT);

    Serial.println("\n>>> MINIGAME: PLAY STARTED <<<");
    Serial.println("Look at prompt: Press [1] for LEFT, [2] for RIGHT!");
}

void updatePlayGame() {
    unsigned long now = millis();

    // 1. Keep Pet GIF playing
    if (gifLoaded && now >= nextFrameTime) {
        int iDelay = 0;
        if (!gif.playFrame(true, &iDelay)) {
            loadPetGif(playHappyMoment ? EMOTION_HAPPY : (playTargetDir == 0 ? EMOTION_PLAY_LEFT : EMOTION_PLAY_RIGHT));
        } else {
            nextFrameTime = now + iDelay;
        }
    }

    // 2. Handle happy score moment (split second!)
    if (playHappyMoment) {
        if (now >= playHappyUntil) {
            playHappyMoment = false;
            playRoundsLeft--;
            if (playRoundsLeft > 0) {
                playTargetDir = random(2);
                petDrawX = 0;
                gfx->fillRect(0, 37, LCD_WIDTH, 168, COLOR_PET_BG);
                loadPetGif(playTargetDir == 0 ? EMOTION_PLAY_LEFT : EMOTION_PLAY_RIGHT);
            } else {
                // Game complete
                currentMode = MODE_PET;
                petDrawX = PET_GIF_X;
                petDrawY = PET_GIF_Y;

                pet.happiness = min(HAPPINESS_MAX, pet.happiness + 30);
                pet.energy = max(0, pet.energy - 10);
                pet.triggerEmotionOverride(EMOTION_HAPPY, 4000);
                pet.setStatus(playScore >= 2 ? "You matched me! Yay!" : "Good try! Again soon!", 3500);

                drawPetScreen(true);
                loadPetGif(EMOTION_HAPPY);
                savePetState();
                printPetStatusSerial();
                return;
            }
        }
        return; // Keep showing happy animation while celebrating
    }

    // 3. Handle brief pause after mismatch
    if (playNextRoundTime > 0) {
        if (now >= playNextRoundTime) {
            playNextRoundTime = 0;
            playRoundsLeft--;
            if (playRoundsLeft > 0) {
                playTargetDir = random(2);
                petDrawX = 0;
                gfx->fillRect(0, 37, LCD_WIDTH, 168, COLOR_PET_BG);
                loadPetGif(playTargetDir == 0 ? EMOTION_PLAY_LEFT : EMOTION_PLAY_RIGHT);
            } else {
                currentMode = MODE_PET;
                petDrawX = PET_GIF_X;
                petDrawY = PET_GIF_Y;

                pet.happiness = min(HAPPINESS_MAX, pet.happiness + 30);
                pet.energy = max(0, pet.energy - 10);
                pet.triggerEmotionOverride(playScore >= 2 ? EMOTION_HAPPY : EMOTION_IDLE, 4000);
                pet.setStatus(playScore >= 2 ? "You matched me! Yay!" : "Good try! Again soon!", 3500);

                drawPetScreen(true);
                loadPetGif(playScore >= 2 ? EMOTION_HAPPY : EMOTION_IDLE);
                savePetState();
                printPetStatusSerial();
                return;
            }
        }
        return;
    }

    // 4. Large arrows pointing left/right (drawn on fur, excluded in GIFDraw so zero Z-fight)
    if (playTargetDir == 0) {
        // Arrow LEFT on left side of pet
        gfx->fillTriangle(8, 108, 38, 86, 38, 130, COLOR_HAPPY);
        gfx->fillRect(38, 98, 14, 20, COLOR_HAPPY);
        gfx->fillRect(186, 84, 50, 48, COLOR_PET_BG); // Clear right
    } else {
        // Arrow RIGHT on right side of pet
        gfx->fillTriangle(232, 108, 202, 86, 202, 130, COLOR_HAPPY);
        gfx->fillRect(188, 98, 14, 20, COLOR_HAPPY);
        gfx->fillRect(6, 84, 50, 48, COLOR_PET_BG); // Clear left
    }

    // Bottom round status in TextSize 2
    gfx->fillRect(10, 205, 220, 26, COLOR_PET_BG);
    gfx->setTextColor(COLOR_BLACK);
    gfx->setTextSize(2);
    gfx->setCursor(20, 210);
    gfx->printf("SCORE: %d / 3", playScore);

    delay(20);
}

void handlePlayGameInput(int btnIndex) {
    if (btnIndex != 0 && btnIndex != 1) return;
    if (playHappyMoment || playNextRoundTime > 0) return; // Prevent spamming during transition

    bool correct = (btnIndex == playTargetDir);
    if (correct) {
        playScore++;
        playHappyMoment = true;
        playHappyUntil = millis() + 450; // SPLIT SECOND (450ms)!
        petDrawX = PET_GIF_X; // Center face
        loadPetGif(EMOTION_HAPPY); // Turn HAPPY!

        // Clear arrows and show celebratory text
        gfx->fillRect(0, 37, LCD_WIDTH, 168, COLOR_PET_BG);
        gfx->fillRect(10, 205, 220, 26, COLOR_PET_BG);
        gfx->setTextColor(COLOR_BLACK);
        gfx->setTextSize(2);
        gfx->setCursor(20, 210);
        gfx->printf("SCORE: %d / 3  YAY!", playScore);

        Serial.printf("-> MATCH! Correct direction! Score: %d/3\n", playScore);
    } else {
        Serial.println("-> MISMATCH! Wrong direction.");
        playNextRoundTime = millis() + 500;
        gfx->fillRect(10, 205, 220, 26, COLOR_PET_BG);
        gfx->setTextColor(COLOR_BLACK);
        gfx->setTextSize(2);
        gfx->setCursor(20, 210);
        gfx->printf("SCORE: %d / 3  MISS!", playScore);
    }
}

// ==========================================
// Central Button Input Handler (Debounced)
// ==========================================
void handleButtonPress(int btnIndex) {
    static unsigned long lastBtnPressTime[4] = {0, 0, 0, 0};
    unsigned long now = millis();
    if (now - lastBtnPressTime[btnIndex] < 120) {
        return; // Debounce duplicate triggers within 120ms
    }
    lastBtnPressTime[btnIndex] = now;

    Serial.printf("[INPUT] Button %d triggered (via %s)\n", btnIndex + 1, "HW/Serial");

    if (currentMode == MODE_GAME_FEED) {
        handleFeedGameInput(btnIndex);
        return;
    } else if (currentMode == MODE_GAME_WASH) {
        handleWashGameInput(btnIndex);
        return;
    } else if (currentMode == MODE_GAME_PLAY) {
        handlePlayGameInput(btnIndex);
        return;
    }

    // Main Pet Mode Actions
    switch (btnIndex) {
        case 0: // Button 1: Feed
            if (pet.isSleeping) {
                pet.setStatus("Kekusis is asleep!", 2000);
            } else {
                startFeedGame();
            }
            break;

        case 1: // Button 2: Wash
            if (pet.isSleeping) {
                pet.setStatus("Don't splash water!", 2000);
            } else {
                startWashGame();
            }
            break;

        case 2: // Button 3: Play
            if (pet.isSleeping) {
                pet.setStatus("Shh! Kekusis is napping.", 2000);
            } else if (pet.energy < 15) {
                pet.setStatus("Too tired to play!", 2500);
            } else {
                startPlayGame();
            }
            break;

        case 3: // Button 4: Sleep / Wake Toggle
            pet.isSleeping = !pet.isSleeping;
            if (pet.isSleeping) {
                pet.setStatus("Goodnight! Zzz...", 3000);
                Serial.println("Kekusis is now SLEEPING.");
            } else {
                pet.setStatus("Good morning!", 2500);
                Serial.println("Kekusis is now AWAKE.");
            }
            drawPetScreen(true);
            savePetState();
            break;
    }
}

// ==========================================
// Serial Command Processor & Time Sync
// ==========================================
void handleSerialCommands() {
    while (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() == 0) continue;

        if (cmd == "1" || cmd == "btn1" || cmd == "BTN1") {
            handleButtonPress(0);
        } else if (cmd == "2" || cmd == "btn2" || cmd == "BTN2") {
            handleButtonPress(1);
        } else if (cmd == "3" || cmd == "btn3" || cmd == "BTN3") {
            handleButtonPress(2);
        } else if (cmd == "4" || cmd == "btn4" || cmd == "BTN4") {
            handleButtonPress(3);
        } else if (cmd.startsWith("time ") || cmd.startsWith("TIME ")) {
            // Real-time synchronization & offline decay check
            unsigned long epoch = strtoul(cmd.substring(5).c_str(), NULL, 10);
            if (epoch > 100000) {
                struct timeval tv = { (time_t)epoch, 0 };
                settimeofday(&tv, NULL);

                prefs.begin("kekusis", false);
                unsigned long lastSavedEpoch = prefs.getULong("last_time", 0);
                prefs.end();

                if (!timeSynchronized && lastSavedEpoch > 0 && epoch > lastSavedEpoch) {
                    unsigned long elapsed = epoch - lastSavedEpoch;
                    Serial.printf("[TIME] Synced! Kekusis was powered down for %lu minutes.\n", elapsed / 60);
                    pet.applyOfflineDecay(elapsed);
                    drawPetScreen(true);
                }
                timeSynchronized = true;
                savePetState();
            }
        } else if (cmd == "feed") {
            startFeedGame();
        } else if (cmd == "wash") {
            startWashGame();
        } else if (cmd == "play") {
            startPlayGame();
        } else if (cmd == "sleep") {
            handleButtonPress(3);
        } else if (cmd == "status") {
            printPetStatusSerial();
        } else if (cmd == "save") {
            savePetState();
            Serial.println("State saved to NVS.");
        } else if (cmd == "help" || cmd == "?") {
            printSerialHelp();
        } else if (cmd.startsWith("anim ") || cmd.startsWith("ANIM ")) {
            String animName = cmd.substring(5);
            animName.trim();
            animName.toLowerCase();
            PetEmotion emo = EMOTION_IDLE;
            if (animName == "happy") emo = EMOTION_HAPPY;
            else if (animName == "hungry") emo = EMOTION_HUNGRY;
            else if (animName == "dirty") emo = EMOTION_DIRTY;
            else if (animName == "eating" || animName == "eat") emo = EMOTION_EATING;
            else if (animName == "sleeping" || animName == "sleep") emo = EMOTION_SLEEPING;
            else if (animName == "washing" || animName == "wash") emo = EMOTION_WASHING;
            else if (animName == "playing" || animName == "play") emo = EMOTION_PLAYING;
            else emo = EMOTION_IDLE;

            currentMode = MODE_PET;
            petDrawX = PET_GIF_X;
            petDrawY = PET_GIF_Y;
            pet.triggerEmotionOverride(emo, 20000); // Override for 20s
            loadPetGif(emo);
            drawPetScreen(true);
            Serial.printf("Playing animation: %s\n", animName.c_str());
            printPetStatusSerial();
        } else if (cmd.startsWith("set stats ")) {
            int h, c, p, e;
            if (sscanf(cmd.substring(10).c_str(), "%d %d %d %d", &h, &c, &p, &e) == 4) {
                pet.hunger = constrain(h, 0, 100);
                pet.cleanliness = constrain(c, 0, 100);
                pet.happiness = constrain(p, 0, 100);
                pet.energy = constrain(e, 0, 100);
                savePetState();
                drawPetScreen(true);
                Serial.printf("Stats updated -> H:%d C:%d P:%d E:%d\n", pet.hunger, pet.cleanliness, pet.happiness, pet.energy);
                printPetStatusSerial();
            }
        } else if (cmd.startsWith("set hunger ")) {
            pet.hunger = constrain(cmd.substring(11).toInt(), 0, 100);
            savePetState();
            drawPetScreen(true);
            Serial.printf("Hunger set to %d\n", pet.hunger);
            printPetStatusSerial();
        } else if (cmd.startsWith("set clean ")) {
            pet.cleanliness = constrain(cmd.substring(10).toInt(), 0, 100);
            savePetState();
            drawPetScreen(true);
            Serial.printf("Cleanliness set to %d\n", pet.cleanliness);
            printPetStatusSerial();
        } else if (cmd.startsWith("set happy ")) {
            pet.happiness = constrain(cmd.substring(10).toInt(), 0, 100);
            savePetState();
            drawPetScreen(true);
            Serial.printf("Happiness set to %d\n", pet.happiness);
            printPetStatusSerial();
        } else if (cmd.startsWith("set energy ")) {
            pet.energy = constrain(cmd.substring(11).toInt(), 0, 100);
            savePetState();
            drawPetScreen(true);
            Serial.printf("Energy set to %d\n", pet.energy);
            printPetStatusSerial();
        } else {
            Serial.printf("Unknown command: '%s'. Type 'help' for options.\n", cmd.c_str());
        }
    }
}

void printSerialHelp() {
    Serial.println("\n========== KEKUSIS TAMAGOTCHI COMMANDS ==========");
    Serial.println("  1 (or 'btn1')    : Emulate Button 1 [FEED / Action 1]");
    Serial.println("  2 (or 'btn2')    : Emulate Button 2 [WASH / Action 2]");
    Serial.println("  3 (or 'btn3')    : Emulate Button 3 [PLAY / Action 3]");
    Serial.println("  4 (or 'btn4')    : Emulate Button 4 [SLEEP / Action 4]");
    Serial.println("  status           : Print current stats & mood");
    Serial.println("  TIME <epoch>     : Sync real-world clock (auto-sent by PC)");
    Serial.println("  save             : Save pet state to flash memory");
    Serial.println("  feed / wash / play / sleep");
    Serial.println("==================================================");
}

void printPetStatusSerial() {
    const char *emotionNames[] = {"IDLE", "HAPPY", "HUNGRY", "DIRTY", "EATING", "WASHING", "SLEEPING", "PLAYING"};
    Serial.printf("\n[PET STATUS] Kekusis -> Hunger: %d%% | Clean: %d%% | Happy: %d%% | Energy: %d%% | Mood: %s | Sleeping: %s\n",
                  pet.hunger, pet.cleanliness, pet.happiness, pet.energy,
                  emotionNames[pet.currentEmotion], pet.isSleeping ? "YES" : "NO");
}

// ==========================================
// Setup & Main Loop
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(400);

    Serial.println("\n==========================================");
    Serial.println("       KEKUSIS TAMAGOTCHI INITIALIZING    ");
    Serial.println("==========================================");

    // Initialize Physical Buttons
    for (int i = 0; i < 4; i++) {
        pinMode(buttons[i].pin, INPUT_PULLUP);
    }

    // Initialize Backlight if enabled
    if (TFT_BL >= 0) {
        pinMode(TFT_BL, OUTPUT);
        digitalWrite(TFT_BL, HIGH);
    }

    // Initialize ST7789 Display
    if (!gfx->begin()) {
        Serial.println("ERROR: Display initialization failed!");
    } else {
        Serial.println("Display initialized (240x240 ST7789).");
    }

    // Initialize AnimatedGIF Decoder
    gif.begin(LITTLE_ENDIAN_PIXELS);

    // Initialize Pet state & load saved NVS state
    pet.init();
    loadPetState();

    // Initial draw
    drawPetScreen(true);
    loadPetGif(pet.currentEmotion);

    printSerialHelp();
    printPetStatusSerial();
}

void loop() {
    unsigned long now = millis();

    // 1. Check Serial Commands & Time Sync from PC
    handleSerialCommands();

    // 2. Poll Physical Buttons with debounce
    for (int i = 0; i < 4; i++) {
        int reading = digitalRead(buttons[i].pin);
        if (reading != buttons[i].lastState) {
            buttons[i].lastDebounceTime = now;
        }
        if ((now - buttons[i].lastDebounceTime) > BTN_DEBOUNCE_MS) {
            if (reading != buttons[i].currentState) {
                buttons[i].currentState = reading;
                if (buttons[i].currentState == LOW) {
                    handleButtonPress(i);
                }
            }
        }
        buttons[i].lastState = reading;
    }

    // 3. Handle Active Minigames
    if (currentMode == MODE_GAME_FEED) {
        updateFeedGame();
        return;
    } else if (currentMode == MODE_GAME_WASH) {
        updateWashGame();
        return;
    } else if (currentMode == MODE_GAME_PLAY) {
        updatePlayGame();
        return;
    }

    // 4. Update Pet State & Emotion
    pet.update(now);

    // If emotion changed, load appropriate GIF
    if (pet.currentEmotion != activeGifEmotion) {
        loadPetGif(pet.currentEmotion);
    }

    // 5. Play GIF Frames
    if (gifLoaded && now >= nextFrameTime) {
        int iDelay = 0;
        if (!gif.playFrame(true, &iDelay)) {
            loadPetGif(pet.currentEmotion);
        } else {
            nextFrameTime = now + iDelay;
        }
    }

    // 6. Refresh Status Bar and Speech Bubble periodically
    static unsigned long lastUiUpdate = 0;
    if (now - lastUiUpdate > 1000) {
        lastUiUpdate = now;
        drawStatusBar();
        drawSpeechBubble();
    }

    // 7. Auto-save state to flash memory
    if (now - lastSaveTime > SAVE_INTERVAL_MS) {
        lastSaveTime = now;
        savePetState();
    }
}
