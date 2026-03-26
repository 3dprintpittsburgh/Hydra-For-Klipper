# LED Effects Setup for Hydra

Hydra supports zone-aware LED effects that show each toolhead's state independently. Your LED strip is split into two zones (left for T0, right for T1) with per-state effects.

## LED States

| State | When | Suggested Effect |
|-------|------|-----------------|
| **toolchange** | During carriage switch (global, full strip) | Pulsing gradient |
| **printing** | Tool is actively printing (zone) | Solid bright white |
| **standby** | Tool parked, holding temperature (zone) | Slow breathing warm |
| **preheating** | Tool heating up from cold (zone) | Fast pulsing orange |
| **idle** | Tool cold, inactive (zone) | Off or dim |

## Quick Setup

### 1. Configure Zones in `hydra_variables.cfg`

```ini
# Your neopixel strip name
variable_led_strip_name: "main_leds"

# Split your strip into two zones
variable_led_zone_left_start: 1       # T0 zone: pixels 1-12
variable_led_zone_left_end: 12
variable_led_zone_right_start: 13     # T1 zone: pixels 13-24
variable_led_zone_right_end: 24

# Effect names per state (must match [led_effect] section names)
variable_led_effect_toolchange: "hydra_toolchange"
variable_led_effect_printing: "hydra_printing"
variable_led_effect_standby: "hydra_standby"
variable_led_effect_preheating: "hydra_preheating"
variable_led_effect_idle: ""           # Empty = LEDs off for this state
```

### 2. Define LED Effects in `printer.cfg`

Requires [klipper-led_effect](https://github.com/julianschill/klipper-led_effect) plugin.

```ini
# Your LED hardware
[neopixel main_leds]
pin: PB0
chain_count: 24
color_order: GRB
initial_RED: 0.3
initial_GREEN: 0
initial_BLUE: 0.3

# --- Global effects (full strip) ---

[led_effect hydra_toolchange]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds
layers:
    gradient 0.5 1 top (0.5,0,1),(0,0.8,1)

# --- T0 zone effects (left side, pixels 1-12) ---

[led_effect hydra_printing]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds (1-12)
layers:
    static 0 0 top (1,1,1)

[led_effect hydra_standby]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds (1-12)
layers:
    breathing 3 0 top (1,0.5,0)

[led_effect hydra_preheating]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds (1-12)
layers:
    breathing 1 0 top (1,0.3,0)

# --- T1 zone effects (right side, pixels 13-24) ---
# Duplicate the above effects but targeting different pixels:

[led_effect hydra_printing_t1]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds (13-24)
layers:
    static 0 0 top (1,1,1)

[led_effect hydra_standby_t1]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds (13-24)
layers:
    breathing 3 0 top (0,0.5,1)

[led_effect hydra_preheating_t1]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds (13-24)
layers:
    breathing 1 0 top (0,0.3,1)
```

**Important:** The LED Effects plugin applies effects to specific pixel ranges defined in each `[led_effect]` section. Hydra calls effects by name - the pixel targeting is in the effect definition, not in Hydra's macros.

### 3. Per-Zone Effect Naming Convention

For per-zone effects, you have two approaches:

**Approach A: Shared effect names (simpler)**

Use the same effect name for both zones. The effect definition targets the full strip. Both zones show the same pattern:

```ini
variable_led_effect_printing: "hydra_printing"    # Same for both tools

[led_effect hydra_printing]
leds:
    neopixel:main_leds                            # Full strip
```

**Approach B: Per-tool effect names (more control)**

Define separate effects per zone with different pixel ranges and colors. Use Hydra's `_HYDRA_LED_TOOL` macro directly in your user hooks, or modify the effect names to include tool-specific variants.

For maximum control, override `_HYDRA_LED_TOOL` in your printer.cfg:

```ini
[gcode_macro _HYDRA_LED_TOOL]
gcode:
    {% set tool = params.TOOL|default(0)|int %}
    {% set state = params.STATE|default("idle")|string %}

    {% if state == "printing" %}
        {% if tool == 0 %}
            SET_LED_EFFECT EFFECT=hydra_printing STOP=1
            SET_LED_EFFECT EFFECT=hydra_printing
        {% else %}
            SET_LED_EFFECT EFFECT=hydra_printing_t1 STOP=1
            SET_LED_EFFECT EFFECT=hydra_printing_t1
        {% endif %}
    {% elif state == "standby" %}
        {% if tool == 0 %}
            SET_LED_EFFECT EFFECT=hydra_standby
        {% else %}
            SET_LED_EFFECT EFFECT=hydra_standby_t1
        {% endif %}
    {% elif state == "preheating" %}
        {% if tool == 0 %}
            SET_LED_EFFECT EFFECT=hydra_preheating
        {% else %}
            SET_LED_EFFECT EFFECT=hydra_preheating_t1
        {% endif %}
    {% else %}
        # Idle - turn off this zone
        {% set cfg = printer["gcode_macro _HYDRA_CONFIG"] %}
        {% if tool == 0 %}
            {% for i in range(cfg.led_zone_left_start, cfg.led_zone_left_end + 1) %}
                SET_LED LED={cfg.led_strip_name} INDEX={i} RED=0 GREEN=0 BLUE=0
            {% endfor %}
        {% else %}
            {% for i in range(cfg.led_zone_right_start, cfg.led_zone_right_end + 1) %}
                SET_LED LED={cfg.led_strip_name} INDEX={i} RED=0 GREEN=0 BLUE=0
            {% endfor %}
        {% endif %}
    {% endif %}
```

## When LEDs Update

Hydra updates LEDs at these moments:

| Moment | What happens |
|--------|-------------|
| **START_PRINT** heats T0 | T0 zone → preheating |
| **START_PRINT** heats T1 (if dual) | T1 zone → preheating |
| **START_PRINT** temps reached | `_HYDRA_LED_UPDATE` → zones reflect actual state |
| **Toolchange starts** | Global → toolchange effect |
| **Tool parked** | Parked tool's zone → standby or idle |
| **Toolchange completes** | `_HYDRA_LED_UPDATE` → zones reflect new state |
| **END_PRINT** | Global → off |

## Disabling LEDs

Set `led_strip_name` to empty string to disable everything:

```ini
variable_led_strip_name: ""
```

All LED macros check this value and skip entirely when empty.

## Troubleshooting

**"Unknown command SET_LED_EFFECT":**
Install [klipper-led_effect](https://github.com/julianschill/klipper-led_effect) or set all effect names to `""`.

**Only one zone updates:**
Make sure your `[led_effect]` sections target the correct pixel ranges with `(start-end)` syntax.

**LEDs stuck after print:**
Add `STOP_LED_EFFECTS` to your `_HYDRA_USER_END_PRINT` override, or check that END_PRINT is being called.

**Effects overlap/flash:**
The `_HYDRA_LED_TOOL` macro calls `STOP=1` before starting a new effect. If effects still overlap, check that you don't have `autostart: true` on any Hydra effects.
