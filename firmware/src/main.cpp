#include <Arduino.h>
#include <LovyanGFX.hpp>
#include <AnimatedGIF.h>
#include <Preferences.h>
#include <time.h>
#include <sys/time.h>

#include "config.h"
#include "LGFX_Config.h"
#include "pet_gifs.h"
#include "treat_sprites.h"
#include "PetState.h"

// ==========================================
// Framebuffer renderer
//
// Everything is drawn into a RAM sprite first, then pushed to the ST7789 in
// one operation. This removes the two classes of artifacts the old immediate
// renderer suffered from:
//   * flashing: partially drawn frames were visible on the panel
//   * ghosting: moving sprites were "erased" with a solid color over a GIF
//     frame, leaving holes when the GIF did not repaint that region
// ==========================================
#define FRAME_INTERVAL_MS 33
#define SAVE_INTERVAL_MS  30000

static LGFX lcd;
static lgfx::LGFX_Sprite scene(&lcd);
static uint16_t scenePixels[LCD_WIDTH * LCD_HEIGHT] __attribute__((aligned(4)));

static Preferences prefs;
static Pet pet;

// RGB565 colors used throughout the UI.
#define COLOR_PET_BG      0x9CD3
#define COLOR_BG          0x18E4
#define COLOR_WHITE       0xFFFF
#define COLOR_BLACK       0x0000
#define COLOR_HUNGER      0xFD00
#define COLOR_CLEAN       0x5EBF
#define COLOR_HAPPY       0xFA08
#define COLOR_ENERGY      0xFFE0
#define COLOR_BORDER      0x4A69
#define COLOR_RED         0xF800
#define COLOR_SOAP        0xFBB8
#define COLOR_SOAP_HI     0xFE19
#define COLOR_BUBBLE_RIM  0xF81F

static const int laneX[4] = {34, 91, 149, 206};

struct ButtonInput {
    uint8_t pin;
    bool lastState;
    bool currentState;
    unsigned long lastChange;
};

static ButtonInput buttons[4] = {
    {PIN_BTN_FEED,  HIGH, HIGH, 0},
    {PIN_BTN_WASH,  HIGH, HIGH, 0},
    {PIN_BTN_PLAY,  HIGH, HIGH, 0},
    {PIN_BTN_SLEEP, HIGH, HIGH, 0}
};

// ==========================================
// GIF layer: keeps a complete RGB565 canvas
//
// AnimatedGIF normally calls us with changed scanlines only. We apply those
// lines (including transparency and disposal-to-background) to our own full
// frame canvas. Because the whole canvas is redrawn every scene frame, no
// stale pixels can survive a move or a partial GIF update.
// ==========================================
class GifLayer {
public:
    uint16_t canvas[PET_GIF_W * PET_GIF_H];

    GifLayer()
        : decoder(), active(EMOTION_IDLE), loaded(false), firstLine(true),
          nextFrameAt(0), prevX1(0), prevY1(0), prevX2(PET_GIF_W - 1),
          prevY2(PET_GIF_H - 1), prevDisposal2(false),
          prevBackground(COLOR_PET_BG), curDisposal2(false),
          curBackground(COLOR_PET_BG), curX1(0), curY1(0), curX2(-1), curY2(-1),
          reopening(false)
    {}

    void begin() {
        instance = this;
        decoder.begin(GIF_PALETTE_RGB565_LE);
        clearCanvas(COLOR_PET_BG);
    }

    bool isLoaded() const { return loaded; }
    PetEmotion emotion() const { return active; }

    void open(PetEmotion emotionToOpen) {
        if (loaded) {
            decoder.close();
            loaded = false;
        }

        active = emotionToOpen;
        size_t length = 0;
        const uint8_t *data = dataFor(emotionToOpen, length);
        if (!data || length == 0) return;

        if (decoder.open(const_cast<uint8_t *>(data), (int)length, lineCallback)) {
            loaded = true;
            clearCanvas(COLOR_PET_BG);
            prevX1 = 0;
            prevY1 = 0;
            prevX2 = PET_GIF_W - 1;
            prevY2 = PET_GIF_H - 1;
            prevDisposal2 = false;
            decodeFrame();
        }
    }

    void update(unsigned long now) {
        if (loaded && now >= nextFrameAt) decodeFrame();
    }

    void draw(int x, int y) const {
        scene.pushImage(x, y, PET_GIF_W, PET_GIF_H, canvas);
    }

private:
    static GifLayer *instance;
    AnimatedGIF decoder;
    PetEmotion active;
    bool loaded;
    bool firstLine;
    unsigned long nextFrameAt;

    int prevX1, prevY1, prevX2, prevY2;
    bool prevDisposal2;
    uint16_t prevBackground;

    bool curDisposal2;
    uint16_t curBackground;
    int curX1, curY1, curX2, curY2;
    bool reopening;

    static void lineCallback(GIFDRAW *draw) {
        if (instance) instance->applyLine(draw);
    }

    static const uint8_t *dataFor(PetEmotion value, size_t &length) {
        switch (value) {
            case EMOTION_HAPPY:   length = gif_happy_len;   return gif_happy;
            case EMOTION_HUNGRY:  length = gif_hungry_len;  return gif_hungry;
            case EMOTION_DIRTY:   length = gif_dirty_len;   return gif_dirty;
            case EMOTION_EATING:  length = gif_eating_len;  return gif_eating;
            case EMOTION_WASHING: length = gif_washing_len; return gif_washing;
            case EMOTION_SLEEPING:length = gif_sleeping_len;return gif_sleeping;
            case EMOTION_PLAYING: length = gif_playing_len; return gif_playing;
            case EMOTION_PLAY_LEFT: length = gif_play_left_len; return gif_play_left;
            case EMOTION_PLAY_RIGHT:length = gif_play_right_len;return gif_play_right;
            case EMOTION_IDLE:
            default:              length = gif_idle_len;    return gif_idle;
        }
    }

    void clearCanvas(uint16_t color) {
        for (int i = 0; i < PET_GIF_W * PET_GIF_H; i++) canvas[i] = color;
    }

    void fillCanvasRect(int x, int y, int w, int h, uint16_t color) {
        int x1 = constrain(x, 0, PET_GIF_W - 1);
        int y1 = constrain(y, 0, PET_GIF_H - 1);
        int x2 = constrain(x + w - 1, 0, PET_GIF_W - 1);
        int y2 = constrain(y + h - 1, 0, PET_GIF_H - 1);
        for (int row = y1; row <= y2; row++) {
            uint16_t *dest = &canvas[row * PET_GIF_W];
            for (int col = x1; col <= x2; col++) dest[col] = color;
        }
    }

    void applyLine(GIFDRAW *draw) {
        if (firstLine) {
            // Dispose the previous frame before drawing the new one.
            if (prevDisposal2 && prevX2 >= prevX1 && prevY2 >= prevY1) {
                fillCanvasRect(prevX1, prevY1,
                               prevX2 - prevX1 + 1, prevY2 - prevY1 + 1,
                               prevBackground);
            }
            firstLine = false;
            curX1 = PET_GIF_W;
            curY1 = PET_GIF_H;
            curX2 = -1;
            curY2 = -1;
            curDisposal2 = (draw->ucDisposalMethod == 2);
            curBackground = draw->pPalette
                          ? draw->pPalette[draw->ucBackground & 0xFF]
                          : COLOR_PET_BG;
        }

        int frameX = draw->iX;
        int frameY = draw->iY + draw->y;
        int width = draw->iWidth;

        curX1 = min(curX1, frameX);
        curX2 = max(curX2, frameX + width - 1);
        curY1 = min(curY1, frameY);
        curY2 = max(curY2, frameY);

        const uint8_t transparent = draw->ucHasTransparency
                                  ? draw->ucTransparent : 0xFF;
        for (int i = 0; i < width; i++) {
            int px = frameX + i;
            if (px < 0 || px >= PET_GIF_W || frameY < 0 || frameY >= PET_GIF_H) {
                continue;
            }
            uint8_t index = draw->pPixels[i];
            if (draw->ucHasTransparency && index == transparent) continue;
            canvas[frameY * PET_GIF_W + px] = draw->pPalette[index];
        }

        // Remember this frame's rectangle for the next frame's disposal.
        prevX1 = curX1;
        prevY1 = curY1;
        prevX2 = curX2;
        prevY2 = curY2;
        prevDisposal2 = curDisposal2;
        prevBackground = curBackground;
    }

    void decodeFrame() {
        firstLine = true;
        int delayMs = 0;
        int result = decoder.playFrame(true, &delayMs);
        if (result <= 0 && !reopening) {
            // End of animation: reopen so decoder state is fully reset.
            reopening = true;
            open(active);          // decodes the first frame itself
            reopening = false;
            return;
        }
        if (result <= 0) delayMs = 100;
        nextFrameAt = millis() + (unsigned long)max(1, delayMs);
    }
};

GifLayer *GifLayer::instance = nullptr;
GifLayer gifLayer;

// ==========================================
// Application state
// ==========================================
static AppMode mode = MODE_PET;
static int petDrawX = PET_GIF_X;
static int petDrawY = PET_GIF_Y;

static unsigned long lastRenderAt = 0;
static unsigned long lastSaveAt = 0;

int petDrawLane();

struct FeedState {
    bool active;
    int lane;
    int x;
    int y;
    int type;
    int speed;
    int spawned;
    int score;
    unsigned long nextSpawnAt;
    unsigned long lastMoveAt;
    unsigned long finishAt;
} feed;

struct WashState {
    bool bubbleActive;
    int currentBubble;
    int bubbleX;
    int bubbleY;
    int bubbleButton;
    int score;
    unsigned long wrongUntil;
    unsigned long finishAt;
    struct Spot { int x, y; bool active; } spots[6];
} wash;

struct PlayState {
    int roundsLeft;
    int score;
    int targetDirection;
    bool celebrating;
    unsigned long celebrateUntil;
    unsigned long nextRoundAt;
} play;

// ==========================================
// Persistence
// ==========================================
void savePetState() {
    prefs.begin("kekusis", false);
    prefs.putInt("hunger", pet.hunger);
    prefs.putInt("clean", pet.cleanliness);
    prefs.putInt("happy", pet.happiness);
    prefs.putInt("energy", pet.energy);
    prefs.putBool("sleep", pet.isSleeping);
    time_t nowSec = time(nullptr);
    if (nowSec > 100000) prefs.putULong("last_time", (unsigned long)nowSec);
    prefs.end();
}

void loadPetState() {
    prefs.begin("kekusis", false);
    pet.hunger = prefs.getInt("hunger", 85);
    pet.cleanliness = prefs.getInt("clean", 90);
    pet.happiness = prefs.getInt("happy", 85);
    pet.energy = prefs.getInt("energy", 95);
    pet.isSleeping = prefs.getBool("sleep", false);
    unsigned long lastSaved = prefs.getULong("last_time", 0);
    prefs.end();

    Serial.printf("[NVS] Loaded Kekusis: H:%d%% C:%d%% P:%d%% E:%d%% (Last Saved: %lu)\n",
                  pet.hunger, pet.cleanliness, pet.happiness, pet.energy, lastSaved);
}

// ==========================================
// Drawing helpers (all target the framebuffer)
// ==========================================
void drawMeter(lgfx::LGFX_Sprite &g, int x, int y, int w, int h,
               int value, uint16_t color, const char *label) {
    g.setTextColor(color);
    g.setTextSize(2);
    g.setCursor(x, y - 2);
    g.print(label);

    int barX = x + 16;
    int barW = w - 16;
    g.drawRect(barX, y + 1, barW, h, COLOR_BORDER);
    g.fillRect(barX + 1, y + 2, barW - 2, h - 2, 0x2124);

    int fillW = (value * (barW - 2)) / 100;
    if (fillW > 0) g.fillRect(barX + 1, y + 2, fillW, h - 2, color);
}

void drawStatusBar(lgfx::LGFX_Sprite &g) {
    g.fillRect(0, 0, LCD_WIDTH, 40, COLOR_PET_BG);
    drawMeter(g, 4, 4, 112, 12, pet.hunger, COLOR_HUNGER, "H");
    drawMeter(g, 124, 4, 112, 12, pet.cleanliness, COLOR_CLEAN, "C");
    drawMeter(g, 4, 22, 112, 12, pet.happiness, COLOR_HAPPY, "P");
    drawMeter(g, 124, 22, 112, 12, pet.energy, COLOR_ENERGY, "E");
}

void drawFooter(lgfx::LGFX_Sprite &g) {
    g.fillRect(0, 200, LCD_WIDTH, 40, COLOR_PET_BG);
    if (mode != MODE_PET) return;

    static const char *labels[4] = {"FEED", "WASH", "PLAY", nullptr};
    const char *sleepLabel = pet.isSleeping ? "WAKE" : "ZZZ";
    uint16_t colors[4] = {COLOR_HUNGER, COLOR_CLEAN, COLOR_HAPPY, COLOR_ENERGY};

    for (int i = 0; i < 4; i++) {
        int bx = 6 + i * 59;
        g.setTextColor(colors[i]);
        g.setTextSize(2);
        g.setCursor(bx, 214);
        g.print(i + 1);

        g.setTextColor(COLOR_BLACK);
        g.setTextSize(1);
        g.setCursor(bx + 14, 222);
        g.print(i == 3 ? sleepLabel : labels[i]);
    }
}

void drawSpeechBubble(lgfx::LGFX_Sprite &g, unsigned long now) {
    g.fillRect(4, 192, LCD_WIDTH - 8, 8, COLOR_PET_BG);
    if (now >= pet.statusMsgEndTime || pet.statusMsg[0] == '\0') return;

    int textWidth = (int)strlen(pet.statusMsg) * 6;
    int tx = max(4, (LCD_WIDTH - textWidth) / 2);
    g.setTextColor(COLOR_BLACK);
    g.setTextSize(1);
    g.setCursor(tx, 192);
    g.print(pet.statusMsg);
}

void drawGameHeader(lgfx::LGFX_Sprite &g, uint16_t color, const char *text) {
    g.fillRect(0, 0, LCD_WIDTH, 36, COLOR_BG);
    g.drawFastHLine(0, 36, LCD_WIDTH, COLOR_BORDER);
    g.setTextColor(color);
    g.setTextSize(2);
    g.setCursor(22, 2);
    g.print(text);
}

void drawTreat(lgfx::LGFX_Sprite &g) {
    if (!feed.active || feed.y < 42) return;
    int type = constrain(feed.type, 0, NUM_TREAT_TYPES - 1);
    const uint16_t *sprite = (const uint16_t *)pgm_read_ptr(&treat_sprites[type]);
    // Treat sprites bake in the fur-gray background. Treat it as a chroma key
    // so falling food shows the animated pet behind it instead of a gray box.
    g.pushImage(feed.x - TREAT_SPRITE_W / 2,
                feed.y - TREAT_SPRITE_H / 2,
                TREAT_SPRITE_W, TREAT_SPRITE_H, sprite,
                (uint16_t)COLOR_TREAT_BG);
}

void drawSoapSpots(lgfx::LGFX_Sprite &g) {
    for (int i = 0; i < 6; i++) {
        if (!wash.spots[i].active) continue;
        int x = wash.spots[i].x;
        int y = wash.spots[i].y;
        g.fillCircle(x, y, 8, COLOR_SOAP);
        g.fillCircle(x - 3, y - 2, 2, COLOR_WHITE);
        g.fillCircle(x + 4, y + 3, 1, COLOR_SOAP_HI);
    }
}

void drawWashBubble(lgfx::LGFX_Sprite &g, unsigned long now) {
    if (!wash.bubbleActive) return;
    int cx = wash.bubbleX;
    int cy = wash.bubbleY;

    g.drawCircle(cx, cy, 18, COLOR_BUBBLE_RIM);
    g.fillCircle(cx, cy, 16, COLOR_SOAP);
    g.fillCircle(cx - 5, cy - 5, 3, COLOR_WHITE);

    g.setTextColor(COLOR_WHITE);
    g.setTextSize(2);
    g.setCursor(cx - 5, cy - 7);
    g.print(wash.bubbleButton + 1);

    if (now < wash.wrongUntil) {
        g.drawCircle(cx, cy, 21, COLOR_RED);
    }
}

void drawPlayArrows(lgfx::LGFX_Sprite &g) {
    if (play.celebrating || play.nextRoundAt != 0) return;
    // Outline-only arrows: the animated character shows through the arrow
    // instead of being covered by a solid shape on the fur-gray background.
    if (play.targetDirection == 0) {
        g.drawTriangle(8, 108, 38, 86, 38, 130, COLOR_HAPPY);
        g.drawTriangle(9, 108, 37, 88, 37, 128, COLOR_HAPPY);
        g.drawRect(38, 98, 14, 20, COLOR_HAPPY);
    } else {
        g.drawTriangle(232, 108, 202, 86, 202, 130, COLOR_HAPPY);
        g.drawTriangle(231, 108, 203, 88, 203, 128, COLOR_HAPPY);
        g.drawRect(188, 98, 14, 20, COLOR_HAPPY);
    }
}

void drawPlayScore(lgfx::LGFX_Sprite &g) {
    g.fillRect(10, 205, 220, 26, COLOR_PET_BG);
    g.setTextColor(COLOR_BLACK);
    g.setTextSize(2);
    g.setCursor(20, 210);
    g.printf("SCORE: %d / 3", play.score);
    if (play.celebrating || play.nextRoundAt != 0) {
        g.setTextSize(1);
        g.setCursor(166, 214);
        g.print(play.celebrating ? "YAY!" : "MISS!");
    }
}

void render(unsigned long now) {
    scene.fillScreen(COLOR_PET_BG);

    switch (mode) {
        case MODE_PET:
            drawStatusBar(scene);
            gifLayer.draw(petDrawX, petDrawY);
            drawSpeechBubble(scene, now);
            drawFooter(scene);
            break;

        case MODE_GAME_FEED:
            drawGameHeader(scene, COLOR_HUNGER, "FEED KEKUSIS!");
            scene.setTextColor(COLOR_HUNGER);
            scene.setTextSize(2);
            scene.setCursor(48, 20);
            scene.printf("SCORE: %d / 8", feed.score);
            gifLayer.draw(petDrawX, petDrawY);
            drawTreat(scene);
            break;

        case MODE_GAME_WASH:
            drawGameHeader(scene, COLOR_CLEAN, "WASH KEKUSIS!");
            scene.setTextColor(COLOR_CLEAN);
            scene.setTextSize(2);
            scene.setCursor(48, 20);
            scene.printf("SCRUB: %d / 6", wash.score);
            gifLayer.draw(petDrawX, petDrawY);
            drawSoapSpots(scene);
            drawWashBubble(scene, now);
            break;

        case MODE_GAME_PLAY:
            drawGameHeader(scene, COLOR_HAPPY, "MATCH KEKUSIS!");
            gifLayer.draw(petDrawX, petDrawY);
            drawPlayArrows(scene);
            drawPlayScore(scene);
            break;
    }

    // One atomic update: the panel never sees a partially composed frame.
    scene.pushSprite(0, 0);
    lcd.waitDMA();               // scenePixels may be reused next frame
}

// ==========================================
// Minigame state machines (no blocking delays)
// ==========================================
void returnToPetMode(PetEmotion emotion, const char *message,
                     unsigned long messageMs, unsigned long overrideMs) {
    mode = MODE_PET;
    petDrawX = PET_GIF_X;
    petDrawY = PET_GIF_Y;
    pet.triggerEmotionOverride(emotion, overrideMs);
    pet.setStatus(message, messageMs);
    gifLayer.open(emotion);
    savePetState();
}

void startFeedGame() {
    mode = MODE_GAME_FEED;
    feed.lane = 1;
    feed.x = laneX[feed.lane];
    feed.y = 44;
    feed.spawned = 0;
    feed.score = 0;
    feed.active = false;
    feed.nextSpawnAt = millis() + 300;
    feed.lastMoveAt = millis();
    feed.finishAt = 0;
    petDrawX = laneX[feed.lane] - PET_GIF_W / 2;
    petDrawY = 88;
    gifLayer.open(EMOTION_IDLE);

    Serial.println("\n>>> MINIGAME: FAST FALLING TREATS STARTED <<<");
    Serial.println("Treats falling! Press [1], [2], [3], [4] to catch them!");
}

void updateFeedGame(unsigned long now) {
    if (feed.finishAt != 0 && now >= feed.finishAt) {
        bool success = feed.score >= 4;
        char summary[32];
        snprintf(summary, sizeof(summary), "Caught %d/%d! Yum!", feed.score, 8);
        returnToPetMode(success ? EMOTION_HAPPY : EMOTION_IDLE,
                        summary, 3000, 3500);
        return;
    }

    if (!feed.active && feed.spawned < 8 && now >= feed.nextSpawnAt) {
        feed.active = true;
        int offset = 1 + random(3);
        feed.lane = (feed.lane < 0) ? random(4) : (feed.lane + offset) % 4;
        feed.x = laneX[feed.lane];
        feed.y = 44;
        feed.type = random(NUM_TREAT_TYPES);
        feed.speed = 3 + (feed.spawned / 4);
        feed.spawned++;
        feed.lastMoveAt = now;
        Serial.printf("-> Treat #%d falling in Lane %d! (Speed: %d)\n",
                      feed.spawned, feed.lane + 1, feed.speed);
    }

    if (!feed.active && feed.spawned >= 8 && feed.finishAt == 0) {
        feed.finishAt = now + 400;
    }

    if (!feed.active) return;

    unsigned long dt = now - feed.lastMoveAt;
    feed.lastMoveAt = now;
    if (dt > 50) dt = 50;                 // clamp after long serial/Task stalls
    int previousY = feed.y;
    feed.y += (feed.speed * (int)dt) / 16;

    bool crossedCatchBand = previousY <= 165 && feed.y >= 135;
    if (crossedCatchBand && feed.lane == petDrawLane()) {
        feed.active = false;
        feed.score++;
        pet.hunger = min(HUNGER_MAX, pet.hunger + 14);
        pet.happiness = min(HAPPINESS_MAX, pet.happiness + 8);
        pet.triggerEmotionOverride(EMOTION_HAPPY, 450);
        gifLayer.open(EMOTION_HAPPY);
        feed.nextSpawnAt = now + 160;
        Serial.printf("-> YUM! Caught in Lane %d! Score: %d/%d\n",
                      feed.lane + 1, feed.score, 8);
    } else if (feed.y > 180) {
        feed.active = false;
        feed.nextSpawnAt = now + 140;
        Serial.printf("-> MISSED in Lane %d!\n", feed.lane + 1);
    }
}

int petDrawLane() {
    // petDrawX is derived from laneX[petLane] - PET_GIF_W / 2.
    for (int i = 0; i < 4; i++) {
        if (petDrawX == laneX[i] - PET_GIF_W / 2) return i;
    }
    return -1;
}

void handleFeedInput(int button) {
    if (button < 0 || button > 3) return;
    petDrawX = laneX[button] - PET_GIF_W / 2;
    Serial.printf("-> Kekusis moved to Lane %d!\n", button + 1);
}

void spawnWashBubble() {
    wash.bubbleX = 30 + random(180);
    wash.bubbleY = 55 + random(100);
    wash.bubbleButton = random(4);
    wash.bubbleActive = true;
}

void startWashGame() {
    mode = MODE_GAME_WASH;
    wash.score = 0;
    wash.currentBubble = 0;
    wash.bubbleActive = false;
    wash.wrongUntil = 0;
    wash.finishAt = 0;
    for (int i = 0; i < 6; i++) wash.spots[i].active = false;
    petDrawX = PET_GIF_X;
    petDrawY = PET_GIF_Y;
    gifLayer.open(EMOTION_DIRTY);
    spawnWashBubble();

    Serial.println("\n>>> MINIGAME: BUBBLE SCRUB STARTED <<<");
    Serial.println("Pop 6 bubbles! Press the matching button [1-4]!");
}

void updateWashGame(unsigned long now) {
    if (wash.finishAt != 0 && now >= wash.finishAt) {
        pet.cleanliness = min(CLEANLINESS_MAX, pet.cleanliness + 50);
        pet.happiness = min(HAPPINESS_MAX, pet.happiness + 20);
        returnToPetMode(EMOTION_WASHING, "Squeaky clean!", 3500, 4000);
    }
}

void handleWashInput(int button) {
    if (!wash.bubbleActive || button < 0 || button > 3) return;

    if (button != wash.bubbleButton) {
        wash.wrongUntil = millis() + 140;
        Serial.printf("-> WRONG! Need button %d, got %d\n",
                      wash.bubbleButton + 1, button + 1);
        return;
    }

    wash.bubbleActive = false;
    wash.score++;
    wash.spots[wash.currentBubble].x = wash.bubbleX;
    wash.spots[wash.currentBubble].y = wash.bubbleY;
    wash.spots[wash.currentBubble].active = true;
    wash.currentBubble++;

    Serial.printf("-> POPPED Bubble %d! (btn %d) (%d/%d done)\n",
                  wash.currentBubble, button + 1, wash.score, 6);

    if (wash.currentBubble >= 6) {
        wash.finishAt = millis() + 300;
        return;
    }
    spawnWashBubble();
}

void startPlayGame() {
    mode = MODE_GAME_PLAY;
    play.roundsLeft = 3;
    play.score = 0;
    play.targetDirection = random(2);
    play.celebrating = false;
    play.celebrateUntil = 0;
    play.nextRoundAt = 0;
    petDrawX = 0;
    petDrawY = PET_GIF_Y;
    gifLayer.open(play.targetDirection == 0 ? EMOTION_PLAY_LEFT
                                            : EMOTION_PLAY_RIGHT);

    Serial.println("\n>>> MINIGAME: PLAY STARTED <<<");
    Serial.println("Look at the arrow: [1] LEFT, [2] RIGHT!");
}

void advancePlayRound() {
    play.roundsLeft--;
    if (play.roundsLeft <= 0) {
        bool success = play.score >= 2;
        returnToPetMode(success ? EMOTION_HAPPY : EMOTION_IDLE,
                        success ? "You matched me! Yay!" : "Good try! Again soon!",
                        3500, 4000);
        return;
    }
    play.targetDirection = random(2);
    petDrawX = 0;
    gifLayer.open(play.targetDirection == 0 ? EMOTION_PLAY_LEFT
                                            : EMOTION_PLAY_RIGHT);
}

void updatePlayGame(unsigned long now) {
    if (play.celebrating && now >= play.celebrateUntil) {
        play.celebrating = false;
        advancePlayRound();
        return;
    }
    if (play.nextRoundAt != 0 && now >= play.nextRoundAt) {
        play.nextRoundAt = 0;
        advancePlayRound();
    }
}

void handlePlayInput(int button) {
    if (button > 1) return;
    if (play.celebrating || play.nextRoundAt != 0) return;

    if (button == play.targetDirection) {
        play.score++;
        play.celebrating = true;
        play.celebrateUntil = millis() + 450;
        gifLayer.open(EMOTION_HAPPY);
        Serial.printf("-> MATCH! Score: %d/3\n", play.score);
    } else {
        play.nextRoundAt = millis() + 500;
        Serial.println("-> MISMATCH! Wrong direction.");
    }
}

// ==========================================
// Input handling
// ==========================================
void handleButtonPress(int button) {
    static unsigned long lastPress[4] = {0, 0, 0, 0};
    unsigned long now = millis();
    if (now - lastPress[button] < 120) return;
    lastPress[button] = now;

    Serial.printf("[INPUT] Button %d triggered\n", button + 1);

    if (mode == MODE_GAME_FEED) {
        handleFeedInput(button);
        return;
    }
    if (mode == MODE_GAME_WASH) {
        handleWashInput(button);
        return;
    }
    if (mode == MODE_GAME_PLAY) {
        handlePlayInput(button);
        return;
    }

    switch (button) {
        case 0:
            if (pet.isSleeping) pet.setStatus("Kekusis is asleep!", 2000);
            else startFeedGame();
            break;
        case 1:
            if (pet.isSleeping) pet.setStatus("Don't splash water!", 2000);
            else startWashGame();
            break;
        case 2:
            if (pet.isSleeping) pet.setStatus("Shh! Kekusis is napping.", 2000);
            else if (pet.energy < 15) pet.setStatus("Too tired to play!", 2500);
            else startPlayGame();
            break;
        case 3:
            pet.isSleeping = !pet.isSleeping;
            pet.setStatus(pet.isSleeping ? "Goodnight! Zzz..." : "Good morning!",
                          pet.isSleeping ? 3000 : 2500);
            savePetState();
            break;
    }
}

void pollButtons(unsigned long now) {
    for (int i = 0; i < 4; i++) {
        int reading = digitalRead(buttons[i].pin);
        if (reading != buttons[i].lastState) buttons[i].lastChange = now;
        if (now - buttons[i].lastChange > BTN_DEBOUNCE_MS &&
            reading != buttons[i].currentState) {
            buttons[i].currentState = reading;
            if (reading == LOW) handleButtonPress(i);
        }
        buttons[i].lastState = reading;
    }
}

// ==========================================
// Serial command processor
// ==========================================
void printPetStatus() {
    static const char *names[] = {
        "IDLE", "HAPPY", "HUNGRY", "DIRTY", "EATING",
        "WASHING", "SLEEPING", "PLAYING"
    };
    Serial.printf("\n[PET STATUS] Kekusis -> Hunger: %d%% | Clean: %d%% | "
                  "Happy: %d%% | Energy: %d%% | Mood: %s | Sleeping: %s\n",
                  pet.hunger, pet.cleanliness, pet.happiness, pet.energy,
                  names[pet.currentEmotion], pet.isSleeping ? "YES" : "NO");
}

void printHelp() {
    Serial.println("\n========== KEKUSIS TAMAGOTCHI COMMANDS ==========");
    Serial.println("  1..4 or btn1..btn4      : Emulate hardware buttons");
    Serial.println("  feed | wash | play       : Start a minigame");
    Serial.println("  sleep                    : Toggle sleep");
    Serial.println("  status                   : Print current stats & mood");
    Serial.println("  anim <name>              : Force an animation");
    Serial.println("  set <stat> <0-100>       : hunger|clean|happy|energy");
    Serial.println("  set stats <h> <c> <p> <e>");
    Serial.println("  TIME <epoch>             : Sync real-world clock");
    Serial.println("  save | help              : Save state / show this help");
    Serial.println("==================================================");
}

PetEmotion emotionFromName(const String &name) {
    if (name == "happy") return EMOTION_HAPPY;
    if (name == "hungry") return EMOTION_HUNGRY;
    if (name == "dirty") return EMOTION_DIRTY;
    if (name == "eating" || name == "eat") return EMOTION_EATING;
    if (name == "sleeping" || name == "sleep") return EMOTION_SLEEPING;
    if (name == "washing" || name == "wash") return EMOTION_WASHING;
    if (name == "playing" || name == "play") return EMOTION_PLAYING;
    return EMOTION_IDLE;
}

void handleSerialCommands() {
    while (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() == 0) continue;

        if (cmd == "1" || cmd == "btn1" || cmd == "BTN1") handleButtonPress(0);
        else if (cmd == "2" || cmd == "btn2" || cmd == "BTN2") handleButtonPress(1);
        else if (cmd == "3" || cmd == "btn3" || cmd == "BTN3") handleButtonPress(2);
        else if (cmd == "4" || cmd == "btn4" || cmd == "BTN4") handleButtonPress(3);
        else if (cmd.equalsIgnoreCase("status")) printPetStatus();
        else if (cmd.equalsIgnoreCase("save")) {
            savePetState();
            Serial.println("State saved to NVS.");
        }
        else if (cmd.equalsIgnoreCase("help") || cmd == "?") printHelp();
        else if (cmd.equalsIgnoreCase("feed")) startFeedGame();
        else if (cmd.equalsIgnoreCase("wash")) startWashGame();
        else if (cmd.equalsIgnoreCase("play")) startPlayGame();
        else if (cmd.equalsIgnoreCase("sleep")) handleButtonPress(3);
        else if (cmd.startsWith("time ") || cmd.startsWith("TIME ")) {
            unsigned long epoch = strtoul(cmd.substring(5).c_str(), nullptr, 10);
            if (epoch <= 100000) continue;

            struct timeval tv = {(time_t)epoch, 0};
            settimeofday(&tv, nullptr);

            prefs.begin("kekusis", false);
            unsigned long lastSaved = prefs.getULong("last_time", 0);
            prefs.end();

            static bool synchronized = false;
            if (!synchronized && lastSaved > 0 && epoch > lastSaved) {
                Serial.printf("[TIME] Synced! Kekusis was powered down for %lu minutes.\n",
                              (epoch - lastSaved) / 60);
                pet.applyOfflineDecay(epoch - lastSaved);
            }
            synchronized = true;
            savePetState();
        }
        else if (cmd.startsWith("anim ") || cmd.startsWith("ANIM ")) {
            String name = cmd.substring(5);
            name.trim();
            name.toLowerCase();
            PetEmotion emotion = emotionFromName(name);
            mode = MODE_PET;
            petDrawX = PET_GIF_X;
            petDrawY = PET_GIF_Y;
            pet.triggerEmotionOverride(emotion, 20000);
            gifLayer.open(emotion);
            Serial.printf("Playing animation: %s\n", name.c_str());
            printPetStatus();
        }
        else if (cmd.startsWith("set stats ")) {
            int h, c, p, e;
            if (sscanf(cmd.substring(10).c_str(), "%d %d %d %d", &h, &c, &p, &e) == 4) {
                pet.hunger = constrain(h, 0, 100);
                pet.cleanliness = constrain(c, 0, 100);
                pet.happiness = constrain(p, 0, 100);
                pet.energy = constrain(e, 0, 100);
                savePetState();
                printPetStatus();
            }
        }
        else if (cmd.startsWith("set hunger ")) {
            pet.hunger = constrain(cmd.substring(11).toInt(), 0, 100);
            savePetState();
        }
        else if (cmd.startsWith("set clean ")) {
            pet.cleanliness = constrain(cmd.substring(10).toInt(), 0, 100);
            savePetState();
        }
        else if (cmd.startsWith("set happy ")) {
            pet.happiness = constrain(cmd.substring(10).toInt(), 0, 100);
            savePetState();
        }
        else if (cmd.startsWith("set energy ")) {
            pet.energy = constrain(cmd.substring(11).toInt(), 0, 100);
            savePetState();
        }
        else {
            Serial.printf("Unknown command: '%s'. Type 'help' for options.\n", cmd.c_str());
        }
    }
}

// ==========================================
// Setup / main loop
// ==========================================
void setup() {
    Serial.begin(115200);
    delay(200);

    Serial.println("\n==========================================");
    Serial.println("       KEKUSIS TAMAGOTCHI INITIALIZING    ");
    Serial.println("==========================================");

    for (int i = 0; i < 4; i++) pinMode(buttons[i].pin, INPUT_PULLUP);

    lcd.init();
    lcd.setRotation(0);
    lcd.setColorDepth(16);

    scene.setColorDepth(16);
    scene.setBuffer(scenePixels, LCD_WIDTH, LCD_HEIGHT);
    // Firmware sprite/GIF tables are host-order RGB565. Tell LovyanGFX to
    // interpret raw uint16_t buffers that way when blitting into the sprite.
    scene.setSwapBytes(true);
    scene.setTextSize(1);

    gifLayer.begin();
    pet.init();
    loadPetState();
    gifLayer.open(pet.currentEmotion);

    render(millis());
    lastRenderAt = millis();
    printHelp();
    printPetStatus();
    Serial.println("Display initialized (240x240 ST7789, LovyanGFX, framebuffered).");
}

void loop() {
    unsigned long now = millis();

    handleSerialCommands();
    pollButtons(now);

    if (mode == MODE_GAME_FEED) {
        updateFeedGame(now);
    } else if (mode == MODE_GAME_WASH) {
        updateWashGame(now);
    } else if (mode == MODE_GAME_PLAY) {
        updatePlayGame(now);
    } else {
        pet.update(now);
        if (pet.currentEmotion != gifLayer.emotion()) {
            gifLayer.open(pet.currentEmotion);
        }
    }

    gifLayer.update(now);

    if (now - lastRenderAt >= FRAME_INTERVAL_MS) {
        lastRenderAt = now;
        render(now);
    }

    if (now - lastSaveAt >= SAVE_INTERVAL_MS) {
        lastSaveAt = now;
        savePetState();
    }
}
