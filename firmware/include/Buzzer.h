#pragma once
#include <Arduino.h>
#include "config.h"

// ==========================================
// Sound Effects & Melodies
// ==========================================
enum SoundEffect {
    SND_NONE = 0,
    SND_BTN,          // Quick 2200Hz click blip
    SND_FEED_CATCH,   // Happy ascending 3-note munch arpeggio
    SND_WASH_POP,     // Bubbly pitch-shift pop
    SND_WASH_WRONG,   // Low error buzz
    SND_MATCH_WIN,    // 4-note victory chime (C6-E6-G6-C7)
    SND_MATCH_MISS,   // 2-note sad descending buzz
    SND_SLEEP,        // Gentle 3-note lullaby
    SND_WAKE,         // Cheery 3-note morning wake chirp
    SND_PET,          // Cute high chirp / purr
    SND_ALERT         // Attention alert beep
};

struct BuzzerNote {
    uint16_t freq;     // Frequency in Hz (0 = pause/rest)
    uint16_t duration; // Duration in ms
};

class BuzzerManager {
private:
    int _pin;
    bool _enabled;
    const BuzzerNote* _currentMelody;
    int _melodyLen;
    int _currentNoteIdx;
    unsigned long _noteUntil;

    void playNoteDirect(uint16_t freq, uint16_t duration) {
        // 1. Hardware buzzer output (if pin is valid and enabled)
        if (_pin >= 0 && _enabled) {
            if (freq > 0) {
                tone(_pin, freq, duration);
            } else {
                noTone(_pin);
            }
        }
        // 2. Broadcast over Serial for PC Controller emulator
        Serial.printf("[SND] %u %u\n", freq, duration);
    }

public:
    BuzzerManager(int pin = PIN_BUZZER)
        : _pin(pin), _enabled(true), _currentMelody(nullptr),
          _melodyLen(0), _currentNoteIdx(0), _noteUntil(0) {}

    void begin() {
        if (_pin >= 0) {
            pinMode(_pin, OUTPUT);
            digitalWrite(_pin, LOW);
        }
    }

    void setEnabled(bool en) {
        _enabled = en;
        if (!_enabled && _pin >= 0) noTone(_pin);
    }

    bool isEnabled() const { return _enabled; }
    int getPin() const { return _pin; }

    void setPin(int pin) {
        if (_pin >= 0) noTone(_pin);
        _pin = pin;
        begin();
    }

    void play(SoundEffect sfx) {
        static const BuzzerNote sfxBtn[]        = { {2200, 25} };
        static const BuzzerNote sfxFeedCatch[]  = { {988, 35}, {1319, 35}, {1760, 75} };
        static const BuzzerNote sfxWashPop[]    = { {659, 28}, {1175, 45} };
        static const BuzzerNote sfxWashWrong[]  = { {180, 85} };
        static const BuzzerNote sfxMatchWin[]   = { {1046, 35}, {1318, 35}, {1568, 35}, {2093, 110} };
        static const BuzzerNote sfxMatchMiss[]  = { {370, 65}, {260, 100} };
        static const BuzzerNote sfxSleep[]      = { {784, 70}, {659, 70}, {523, 130} };
        static const BuzzerNote sfxWake[]       = { {523, 55}, {659, 55}, {1046, 95} };
        static const BuzzerNote sfxPet[]        = { {1318, 30}, {1760, 50} };
        static const BuzzerNote sfxAlert[]      = { {1480, 55}, {0, 25}, {1480, 55} };

        switch (sfx) {
            case SND_BTN:        playSequence(sfxBtn, 1); break;
            case SND_FEED_CATCH: playSequence(sfxFeedCatch, 3); break;
            case SND_WASH_POP:   playSequence(sfxWashPop, 2); break;
            case SND_WASH_WRONG: playSequence(sfxWashWrong, 1); break;
            case SND_MATCH_WIN:  playSequence(sfxMatchWin, 4); break;
            case SND_MATCH_MISS: playSequence(sfxMatchMiss, 2); break;
            case SND_SLEEP:      playSequence(sfxSleep, 3); break;
            case SND_WAKE:       playSequence(sfxWake, 3); break;
            case SND_PET:        playSequence(sfxPet, 2); break;
            case SND_ALERT:      playSequence(sfxAlert, 3); break;
            default: break;
        }
    }

    void playSequence(const BuzzerNote* melody, int count) {
        if (!melody || count <= 0) return;
        _currentMelody = melody;
        _melodyLen = count;
        _currentNoteIdx = 0;

        playNoteDirect(_currentMelody[0].freq, _currentMelody[0].duration);
        _noteUntil = millis() + _currentMelody[0].duration + 8;
    }

    void playTone(uint16_t freq, uint16_t duration) {
        _currentMelody = nullptr;
        _melodyLen = 0;
        playNoteDirect(freq, duration);
        _noteUntil = millis() + duration;
    }

    void update(unsigned long now) {
        if (_currentMelody && _currentNoteIdx < _melodyLen - 1) {
            if (now >= _noteUntil) {
                _currentNoteIdx++;
                playNoteDirect(_currentMelody[_currentNoteIdx].freq, _currentMelody[_currentNoteIdx].duration);
                _noteUntil = now + _currentMelody[_currentNoteIdx].duration + 8;
            }
        } else if (_currentMelody && _currentNoteIdx >= _melodyLen - 1 && now >= _noteUntil) {
            _currentMelody = nullptr;
            _melodyLen = 0;
        }
    }
};

extern BuzzerManager buzzer;
