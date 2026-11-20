#pragma once

#include <LovyanGFX.hpp>
#include "config.h"

// ==========================================
// LovyanGFX board configuration
// Waveshare ESP32-S3-LCD-1.3 : ST7789 240x240 IPS on SPI
// Pin numbers are shared with the rest of the firmware (see config.h).
// ==========================================
class LGFX : public lgfx::LGFX_Device
{
    lgfx::Panel_ST7789 _panel_instance;
    lgfx::Bus_SPI      _bus_instance;

#if TFT_BL >= 0
    lgfx::Light_PWM _light_instance;
#endif

public:
    LGFX(void)
    {
        { // SPI bus
            auto cfg = _bus_instance.config();

            cfg.spi_host    = SPI2_HOST;          // ESP32-S3: SPI2_HOST / SPI3_HOST
            cfg.spi_mode    = 0;
            cfg.freq_write  = 80000000;
            cfg.freq_read   = 16000000;
            cfg.spi_3wire   = true;               // ST7789 uses D/C + MOSI (no MISO)
            cfg.use_lock    = true;
            cfg.dma_channel = SPI_DMA_CH_AUTO;
            cfg.pin_sclk    = TFT_SCK;
            cfg.pin_mosi    = TFT_MOSI;
            cfg.pin_miso    = -1;
            cfg.pin_dc      = TFT_DC;

            _bus_instance.config(cfg);
            _panel_instance.setBus(&_bus_instance);
        }

        { // ST7789 panel
            auto cfg = _panel_instance.config();

            cfg.pin_cs           = TFT_CS;
            cfg.pin_rst          = TFT_RST;
            cfg.pin_busy         = -1;

            cfg.panel_width      = LCD_WIDTH;
            cfg.panel_height     = LCD_HEIGHT;
            cfg.offset_x         = 0;
            cfg.offset_y         = 0;
            cfg.offset_rotation  = 0;
            cfg.dummy_read_pixel = 8;
            cfg.dummy_read_bits  = 1;
            cfg.readable         = false;
            cfg.invert           = true;          // IPS panel
            cfg.rgb_order        = false;
            cfg.dlen_16bit       = false;
            cfg.bus_shared       = false;

            _panel_instance.config(cfg);
        }

#if TFT_BL >= 0
        { // Backlight (only when a backlight GPIO is configured)
            auto cfg = _light_instance.config();

            cfg.pin_bl      = TFT_BL;
            cfg.invert      = false;
            cfg.freq        = 44100;
            cfg.pwm_channel = 7;

            _light_instance.config(cfg);
            _panel_instance.setLight(&_light_instance);
        }
#endif

        setPanel(&_panel_instance);
    }
};
