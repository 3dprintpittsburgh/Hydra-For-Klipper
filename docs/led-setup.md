# LED Effects Setup for Hydra

Hydra supports LED effects during toolchanges and printing. LEDs are entirely optional - if you don't have LEDs, just leave the config values as empty strings and Hydra will skip all LED calls.

## How It Works

Hydra calls LEDs at two moments during each toolchange:

1. **Toolchange starts** → activates a "waiting" effect (e.g., pulsing gradient)
2. **Toolchange completes** → stops effects and calls a "printing" macro (e.g., solid white)

These are configured via two variables in `hydra_variables.cfg`:

```ini
# LED effects (set to empty string "" to disable)
variable_led_toolchange_effect: "toolchange_wait"
variable_led_printing_macro: "SET_PRINTING_LEDS"
```

## Configuration Options

### Option 1: Full LED Effects (Recommended)

Uses the [LED Effects](https://github.com/julianschill/klipper-led_effect) plugin for animated effects during toolchange, and a simple macro for the steady printing state.

**Requirements:**
- Neopixel/WS2812 LEDs connected to your printer
- [klipper-led_effect](https://github.com/julianschill/klipper-led_effect) plugin installed

**In your printer.cfg:**

```ini
# Your LED hardware
[neopixel main_leds]
pin: PB0                    # Your LED data pin
chain_count: 24
color_order: GRB
initial_RED: 1.0
initial_GREEN: 0.0
initial_BLUE: 1.0

# Toolchange waiting effect - animated gradient while switching tools
[led_effect toolchange_wait]
autostart: false
frame_rate: 24
leds:
    neopixel:main_leds
layers:
    gradient 0.5 1 top (1,1,0),(1,0,1)

# Optional: error effect (auto-starts on Klipper error)
[led_effect critical_error]
leds:
    neopixel:main_leds
layers:
    strobe 1 1.5 add (1.0, 1.0, 1.0)
    breathing 2 0 difference (0.95, 0.0, 0.0)
    static 1 0 top (1.0, 0.0, 0.0)
autostart: false
frame_rate: 24
run_on_error: true

# Steady printing state - called after toolchange completes
[gcode_macro SET_PRINTING_LEDS]
gcode:
    SET_LED LED=main_leds RED=1 GREEN=1 BLUE=1
```

**In hydra_variables.cfg:**

```ini
variable_led_toolchange_effect: "toolchange_wait"
variable_led_printing_macro: "SET_PRINTING_LEDS"
```

### Option 2: Simple Macro-Only (No Plugin Required)

If you don't want to install the LED Effects plugin, you can use plain Klipper LED commands. Create two macros and point Hydra to the "printing" one. The toolchange effect won't animate, but you'll get a color change.

**In your printer.cfg:**

```ini
[neopixel main_leds]
pin: PB0
chain_count: 24
color_order: GRB

# Toolchange color (called as an effect name - requires led_effect plugin)
# Without the plugin, leave toolchange_effect empty and use the printing macro only

# Printing state
[gcode_macro SET_PRINTING_LEDS]
gcode:
    SET_LED LED=main_leds RED=1 GREEN=1 BLUE=1
```

**In hydra_variables.cfg:**

```ini
variable_led_toolchange_effect: ""                # Empty = no toolchange animation
variable_led_printing_macro: "SET_PRINTING_LEDS"  # Still sets LEDs after toolchange
```

### Option 3: Per-Tool Colors

You can make LEDs show which tool is active by creating a smarter printing macro:

```ini
[gcode_macro SET_PRINTING_LEDS]
gcode:
    {% set tool = printer["gcode_macro _HYDRA_CONFIG"].active_tool %}
    {% if tool == 0 %}
        # T0 active - blue
        SET_LED LED=main_leds RED=0.2 GREEN=0.2 BLUE=1.0
    {% elif tool == 1 %}
        # T1 active - cyan
        SET_LED LED=main_leds RED=0.0 GREEN=0.8 BLUE=1.0
    {% else %}
        # No tool / idle - white
        SET_LED LED=main_leds RED=1 GREEN=1 BLUE=1
    {% endif %}
```

### Option 4: No LEDs

Just set both values to empty strings:

```ini
variable_led_toolchange_effect: ""
variable_led_printing_macro: ""
```

Hydra will skip all LED calls entirely.

## How Hydra Calls LEDs Internally

In `hydra.cfg`, the `IDEX_TOOL_CHANGE` macro does:

```python
# Toolchange starts
{% if cfg.led_toolchange_effect %}
    SET_LED_EFFECT EFFECT={cfg.led_toolchange_effect}
{% endif %}

# ... park, switch, restore ...

# Toolchange completes
{% if cfg.led_toolchange_effect %}
    STOP_LED_EFFECTS
{% endif %}
{% if cfg.led_printing_macro %}
    {cfg.led_printing_macro}
{% endif %}
```

The `SET_LED_EFFECT` and `STOP_LED_EFFECTS` commands come from the [klipper-led_effect](https://github.com/julianschill/klipper-led_effect) plugin. The printing macro is a plain Klipper gcode macro that you define.

## Troubleshooting

**"Unknown command SET_LED_EFFECT":**
You have `variable_led_toolchange_effect` set but don't have the LED Effects plugin installed. Either install the plugin or set `variable_led_toolchange_effect: ""` to disable.

**LEDs don't change during toolchange:**
- Check that `variable_led_toolchange_effect` matches the exact name in your `[led_effect]` section
- Check that `variable_led_printing_macro` matches your macro name exactly
- Verify with `SET_LED_EFFECT EFFECT=toolchange_wait` from the console

**LEDs stay in toolchange pattern after print:**
Your END_PRINT or `_HYDRA_USER_END_PRINT` should reset LEDs. Add `STOP_LED_EFFECTS` and your desired idle LED state to the user hook:

```ini
[gcode_macro _HYDRA_USER_END_PRINT]
gcode:
    STOP_LED_EFFECTS
    SET_LED LED=main_leds RED=0.5 GREEN=0 BLUE=0.5    # Idle purple
```
