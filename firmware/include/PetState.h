#pragma once
#include <Arduino.h>
#include "config.h"

enum PetEmotion {
    EMOTION_IDLE = 0,
    EMOTION_HAPPY,
    EMOTION_HUNGRY,
    EMOTION_DIRTY,
    EMOTION_EATING,
    EMOTION_WASHING,
    EMOTION_SLEEPING,
    EMOTION_PLAYING,
    EMOTION_COUNT
};

enum AppMode {
    MODE_PET = 0,
    MODE_GAME_FEED,
    MODE_GAME_WASH,
    MODE_GAME_PLAY
};

struct Pet {
    char name[16];
    int hunger;       // 0 to 100
    int cleanliness;  // 0 to 100
    int happiness;    // 0 to 100
    int energy;       // 0 to 100
    bool isSleeping;
    
    PetEmotion currentEmotion;
    PetEmotion overrideEmotion;
    unsigned long overrideEndTime;
    
    unsigned long lastHungerDecay;
    unsigned long lastCleanDecay;
    unsigned long lastEnergyDecay;
    unsigned long lastEnergyRegen;
    unsigned long nextIdleActionTime;
    
    char statusMsg[32];
    unsigned long statusMsgEndTime;

    void init() {
        strncpy(name, "Kekusis", sizeof(name) - 1);
        hunger = 85;
        cleanliness = 90;
        happiness = 85;
        energy = 95;
        isSleeping = false;
        currentEmotion = EMOTION_IDLE;
        overrideEmotion = EMOTION_IDLE;
        overrideEndTime = 0;
        
        unsigned long now = millis();
        lastHungerDecay = now;
        lastCleanDecay = now;
        lastEnergyDecay = now;
        lastEnergyRegen = now;
        nextIdleActionTime = now + random(IDLE_ACTION_MIN_MS, IDLE_ACTION_MAX_MS);
        
        setStatus("I'm Kekusis!", 3500);
    }

    void setStatus(const char *msg, unsigned long durationMs = 2500) {
        strncpy(statusMsg, msg, sizeof(statusMsg) - 1);
        statusMsg[sizeof(statusMsg) - 1] = '\0';
        statusMsgEndTime = millis() + durationMs;
    }

    void triggerEmotionOverride(PetEmotion emotion, unsigned long durationMs) {
        overrideEmotion = emotion;
        overrideEndTime = millis() + durationMs;
    }

    // Very gentle offline decay when powered down (not aggressive!)
    void applyOfflineDecay(unsigned long elapsedSeconds) {
        if (elapsedSeconds < 60) return; // Ignore under 1 minute

        // Hunger: -1 point every 15 minutes (900s) -> 4 points per hour
        int hungerLoss = elapsedSeconds / 900;
        // Cleanliness: -1 point every 25 minutes (1500s) -> 2.4 points per hour
        int cleanLoss = elapsedSeconds / 1500;

        // Keep a minimum floor of 15% so Kekusis never starves completely while away
        hunger = max(15, hunger - hungerLoss);
        cleanliness = max(15, cleanliness - cleanLoss);
        energy = ENERGY_MAX; // Pet rests while powered down!

        if (hunger < 35 || cleanliness < 35) {
            int happyLoss = elapsedSeconds / 1800; // -1 per 30 minutes
            happiness = max(25, happiness - happyLoss);
        }

        char buffer[32];
        unsigned long hours = elapsedSeconds / 3600;
        if (hours > 0) {
            snprintf(buffer, sizeof(buffer), "Rested %luh! Missed u!", hours);
        } else {
            snprintf(buffer, sizeof(buffer), "Rested %lum! Welcome back!", elapsedSeconds / 60);
        }
        setStatus(buffer, 4000);
    }

    void update(unsigned long now) {
        // Natural stat decay over time while online
        if (!isSleeping) {
            if (now - lastHungerDecay >= HUNGER_DECAY_INTERVAL_MS) {
                lastHungerDecay = now;
                if (hunger > 0) hunger--;
            }
            if (now - lastCleanDecay >= CLEAN_DECAY_INTERVAL_MS) {
                lastCleanDecay = now;
                if (cleanliness > 0) cleanliness--;
            }
            if (now - lastEnergyDecay >= ENERGY_DECAY_INTERVAL_MS) {
                lastEnergyDecay = now;
                if (energy > 0) energy--;
            }
            
            // Happiness drops slowly if hunger or cleanliness is poor
            if (hunger < 25 || cleanliness < 25) {
                if (now % 30000 < 100 && happiness > 0) {
                    happiness--;
                }
            }
        } else {
            // Energy recovers during sleep
            if (now - lastEnergyRegen >= ENERGY_REGEN_INTERVAL_MS) {
                lastEnergyRegen = now;
                if (energy < ENERGY_MAX) energy++;
                if (energy >= ENERGY_MAX) {
                    isSleeping = false;
                    setStatus("Fully rested! Morning!", 3000);
                }
            }
        }

        // Random idle quirks when healthy (rare overrides so idle plays most of the time)
        if (!isSleeping && overrideEndTime <= now && now >= nextIdleActionTime) {
            nextIdleActionTime = now + random(IDLE_ACTION_MIN_MS, IDLE_ACTION_MAX_MS);
            if (hunger > 40 && cleanliness > 40 && energy > 30) {
                int r = random(5); // 1-in-5 chance for an override, idle stays 60%+ of the time
                if (r == 0) {
                    triggerEmotionOverride(EMOTION_HAPPY, 2500);
                    setStatus("*wiggle wiggle*", 2500);
                } else if (r == 1) {
                    triggerEmotionOverride(EMOTION_PLAYING, 2500);
                    setStatus("*doing tricks*", 2500);
                }
                // r == 2, 3, 4 → stays idle (no override)
            }
        }

        // Compute current active emotion
        if (overrideEndTime > now) {
            currentEmotion = overrideEmotion;
        } else if (isSleeping) {
            currentEmotion = EMOTION_SLEEPING;
        } else if (hunger < 25) {
            currentEmotion = EMOTION_HUNGRY;
        } else if (cleanliness < 25) {
            currentEmotion = EMOTION_DIRTY;
        } else if (energy < 20) {
            currentEmotion = EMOTION_SLEEPING;
        } else if (happiness >= 90) {
            currentEmotion = EMOTION_HAPPY;
        } else {
            currentEmotion = EMOTION_IDLE;
        }
    }
};
