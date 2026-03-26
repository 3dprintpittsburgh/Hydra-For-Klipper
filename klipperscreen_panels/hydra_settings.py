import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

HYDRA_CONFIG = "gcode_macro _HYDRA_CONFIG"


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Hydra Settings"
        super().__init__(screen, title)

        self.labels = {}
        self.settings = {}

        # Subscribe for live updates
        self._screen._ws.klippy.object_subscription({
            "objects": {HYDRA_CONFIG: None}
        })

        self._load_settings()

        # Scrollable content for small screens
        scroll = self._gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        grid = Gtk.Grid(column_spacing=5, row_spacing=3)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        grid.set_margin_top(5)

        row = 0

        # Toggle: Wipe Enabled
        row = self._add_toggle(grid, row, "wipe_enabled", "Nozzle Wipe")

        row = self._add_separator(grid, row)

        # Numeric: Retract/Prime
        row = self._add_numeric(grid, row, "retract_distance", "Retract (mm)", 1, 0, 50)
        row = self._add_numeric(grid, row, "prime_distance", "Prime (mm)", 1, 0, 50)

        row = self._add_separator(grid, row)

        # Numeric: Z Hop
        row = self._add_numeric(grid, row, "z_hop", "Z Hop (mm)", 0.5, 0.5, 20)

        row = self._add_separator(grid, row)

        # Numeric: Temperature
        row = self._add_numeric(grid, row, "standby_temp_factor", "Standby Temp %",
                                0.05, 0.5, 1.0, fmt="%.0f%%", scale=100)

        row = self._add_separator(grid, row)

        # Numeric: Wipe
        row = self._add_numeric(grid, row, "wipe_purge_length", "Purge Length (mm)", 5, 0, 100)
        row = self._add_numeric(grid, row, "wipe_cool_time", "Cool Time (s)", 1, 0, 30)

        row = self._add_separator(grid, row)

        # Status label
        self.labels['status'] = Gtk.Label(label="Changes apply immediately. Edit hydra_variables.cfg to persist.")
        self.labels['status'].set_line_wrap(True)
        grid.attach(self.labels['status'], 0, row, 4, 1)

        scroll.add(grid)
        self.content.add(scroll)

    def _load_settings(self):
        """Load settings from config section (always available) then overlay runtime stat if present."""
        try:
            # Always start from config section defaults (reliable)
            cfg = self._printer.get_config_section(HYDRA_CONFIG)
            if cfg:
                for k, v in cfg.items():
                    if k.startswith("variable_"):
                        name = k[9:]
                        try:
                            if v.lower() in ("true", "false"):
                                self.settings[name] = v.lower() == "true"
                            else:
                                self.settings[name] = float(v)
                        except (ValueError, AttributeError):
                            self.settings[name] = v

            # Overlay with runtime values if available (may have been changed via SET_GCODE_VARIABLE)
            stat = self._printer.get_stat(HYDRA_CONFIG)
            if stat:
                for k, v in stat.items():
                    self.settings[k] = v

        except Exception as e:
            logging.warning(f"Hydra Settings: Could not load: {e}")

    def activate(self):
        self._load_settings()
        self._update_all_labels()

    def _add_toggle(self, grid, row, key, label_text):
        label = Gtk.Label(label=label_text, halign=Gtk.Align.START, hexpand=True)
        switch = Gtk.Switch(halign=Gtk.Align.END)
        switch.set_active(bool(self.settings.get(key, False)))
        switch.connect("notify::active", self._on_toggle, key)
        self.labels[key] = switch
        grid.attach(label, 0, row, 2, 1)
        grid.attach(switch, 2, row, 1, 1)
        return row + 1

    def _add_numeric(self, grid, row, key, label_text, step, min_val, max_val, fmt=None, scale=1):
        label = Gtk.Label(label=label_text, halign=Gtk.Align.START)
        val = self.settings.get(key, 0)
        display = self._format_value(val, fmt, scale)

        minus = self._gtk.Button("arrow-down", None, "color1", self.bts)
        minus.connect("clicked", self._on_adjust, key, -step, min_val, max_val, fmt, scale)
        val_label = Gtk.Label(label=display)
        val_label.set_width_chars(8)
        plus = self._gtk.Button("arrow-up", None, "color4", self.bts)
        plus.connect("clicked", self._on_adjust, key, step, min_val, max_val, fmt, scale)

        self.labels[key] = val_label

        grid.attach(label, 0, row, 1, 1)
        grid.attach(minus, 1, row, 1, 1)
        grid.attach(val_label, 2, row, 1, 1)
        grid.attach(plus, 3, row, 1, 1)
        return row + 1

    def _add_separator(self, grid, row):
        grid.attach(Gtk.Separator(hexpand=True), 0, row, 4, 1)
        return row + 1

    def _format_value(self, val, fmt=None, scale=1):
        if fmt and scale != 1:
            return fmt % (val * scale)
        return f"{val}"

    def _on_toggle(self, switch, gparam, key):
        val = switch.get_active()
        klipper_val = "True" if val else "False"
        self._screen._ws.klippy.gcode_script(
            f"SET_GCODE_VARIABLE MACRO=_HYDRA_CONFIG VARIABLE={key} VALUE={klipper_val}"
        )
        self.settings[key] = val
        self.labels['status'].set_label(f"{key} = {val} (runtime)")

    def _on_adjust(self, widget, key, step, min_val, max_val, fmt, scale):
        val = self.settings.get(key, 0)
        val = round(val + step, 3)
        val = max(min_val, min(max_val, val))
        self.settings[key] = val

        self._screen._ws.klippy.gcode_script(
            f"SET_GCODE_VARIABLE MACRO=_HYDRA_CONFIG VARIABLE={key} VALUE={val}"
        )

        display = self._format_value(val, fmt, scale)
        self.labels[key].set_label(display)
        self.labels['status'].set_label(f"{key} = {val} (runtime)")

    def _update_all_labels(self):
        for key, widget in self.labels.items():
            if key == 'status':
                continue
            val = self.settings.get(key, 0)
            if isinstance(widget, Gtk.Switch):
                widget.set_active(bool(val))
            elif isinstance(widget, Gtk.Label):
                widget.set_label(f"{val}")
