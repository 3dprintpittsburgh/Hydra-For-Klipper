import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

HYDRA_CONFIG = "gcode_macro _HYDRA_CONFIG"


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Visual XY Cal"
        super().__init__(screen, title)

        self.step = 0.1
        self.nudge_x = 0.0
        self.nudge_y = 0.0
        self.phase = "idle"

        self.labels = {}
        self.buttons = {}

        grid = Gtk.Grid(column_spacing=10, row_spacing=3)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        grid.set_margin_top(5)

        # === LEFT SIDE: Status and phase controls ===
        left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        left.set_size_request(280, -1)

        self.labels['phase'] = Gtk.Label(label="Press Start to begin")
        self.labels['phase'].set_line_wrap(True)

        self.labels['offset'] = Gtk.Label(label="Offset: X=0.000  Y=0.000")

        self.buttons['start'] = self._gtk.Button("home", "Start: Move T0", "color3", self.bts)
        self.buttons['start'].connect("clicked", self.start_cal)

        self.buttons['switch'] = self._gtk.Button("arrow-right", "Switch to T1", "color4", self.bts)
        self.buttons['switch'].connect("clicked", self.switch_to_t1)
        self.buttons['switch'].set_sensitive(False)

        self.buttons['save'] = self._gtk.Button("complete", "Save & Done", "color3", self.bts)
        self.buttons['save'].connect("clicked", self.save_offsets)
        self.buttons['save'].set_sensitive(False)

        left.pack_start(self.labels['phase'], False, False, 5)
        left.pack_start(self.labels['offset'], False, False, 5)
        left.pack_start(Gtk.Separator(), False, False, 3)
        left.pack_start(self.buttons['start'], False, False, 0)
        left.pack_start(self.buttons['switch'], False, False, 0)
        left.pack_start(self.buttons['save'], False, False, 0)

        # === RIGHT SIDE: Nudge pad ===
        right = Gtk.Grid(column_spacing=2, row_spacing=2, column_homogeneous=True, row_homogeneous=True)
        right.set_hexpand(True)
        right.set_vexpand(True)

        row = 0
        self.step_buttons = {}
        for i, s in enumerate([0.05, 0.1, 0.5, 1.0]):
            btn = self._gtk.Button(None, f"{s}", None, self.bts)
            btn.connect("clicked", self.change_step, s)
            self.step_buttons[s] = btn
            right.attach(btn, i, row, 1, 1)
        self.step_buttons[0.1].get_style_context().add_class("button_active")
        row += 1

        btn_yp = self._gtk.Button("arrow-up", "Y+", "color4", self.bts)
        btn_yp.connect("clicked", self.nudge, "Y", 1)
        right.attach(btn_yp, 1, row, 2, 1)
        row += 1

        btn_xm = self._gtk.Button("arrow-left", "X-", "color1", self.bts)
        btn_xm.connect("clicked", self.nudge, "X", -1)
        btn_rst = self._gtk.Button("refresh", "0,0", "color2", self.bts)
        btn_rst.connect("clicked", self.reset_nudge)
        btn_xp = self._gtk.Button("arrow-right", "X+", "color4", self.bts)
        btn_xp.connect("clicked", self.nudge, "X", 1)
        right.attach(btn_xm, 0, row, 1, 1)
        right.attach(btn_rst, 1, row, 2, 1)
        right.attach(btn_xp, 3, row, 1, 1)
        row += 1

        btn_ym = self._gtk.Button("arrow-down", "Y-", "color1", self.bts)
        btn_ym.connect("clicked", self.nudge, "Y", -1)
        right.attach(btn_ym, 1, row, 2, 1)

        self.nudge_buttons = [btn_yp, btn_ym, btn_xp, btn_xm, btn_rst]
        for b in self.nudge_buttons:
            b.set_sensitive(False)

        grid.attach(left, 0, 0, 1, 1)
        grid.attach(right, 1, 0, 1, 1)
        self.content.add(grid)

    def activate(self):
        self._load_state()

    def _load_state(self):
        try:
            # Subscribe to visual cal macro for updates
            self._screen._ws.klippy.object_subscription({
                "objects": {"gcode_macro CALIBRATE_IDEX_XY_VISUAL": None}
            })
            cal = self._printer.get_stat("gcode_macro CALIBRATE_IDEX_XY_VISUAL")
            if cal and cal.get("active", False):
                self.phase = "nudging"
                self.nudge_x = float(cal.get("nudge_x", 0))
                self.nudge_y = float(cal.get("nudge_y", 0))
                self._set_nudging_state()
        except Exception as e:
            logging.warning(f"Hydra visual cal: Could not load state: {e}")

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if "gcode_macro CALIBRATE_IDEX_XY_VISUAL" in data:
            cal = data["gcode_macro CALIBRATE_IDEX_XY_VISUAL"]
            if "nudge_x" in cal:
                self.nudge_x = float(cal["nudge_x"])
            if "nudge_y" in cal:
                self.nudge_y = float(cal["nudge_y"])
            if "active" in cal:
                if cal["active"] and self.phase != "nudging":
                    self._set_nudging_state()
                elif not cal["active"] and self.phase == "nudging":
                    self._set_idle_state()
            self._update_offset_label()

    def start_cal(self, widget):
        self._screen._ws.klippy.gcode_script("CALIBRATE_IDEX_XY_VISUAL")
        self.phase = "t0_confirm"
        self.labels['phase'].set_label(
            "T0 moved to reference point.\n"
            "Verify nozzle is over your marker.\n"
            "Then press 'Switch to T1'."
        )
        self.buttons['start'].set_sensitive(False)
        self.buttons['switch'].set_sensitive(True)
        self.buttons['save'].set_sensitive(False)
        for b in self.nudge_buttons:
            b.set_sensitive(False)

    def switch_to_t1(self, widget):
        self._screen._ws.klippy.gcode_script("IDEX_VISUAL_SWITCH")
        self.nudge_x = 0.0
        self.nudge_y = 0.0
        self._set_nudging_state()

    def _set_nudging_state(self):
        self.phase = "nudging"
        self.labels['phase'].set_label(
            "T1 at reference point (no offset).\n"
            "Nudge until nozzle aligns with marker."
        )
        self.buttons['start'].set_sensitive(False)
        self.buttons['switch'].set_sensitive(False)
        self.buttons['save'].set_sensitive(True)
        for b in self.nudge_buttons:
            b.set_sensitive(True)
        self._update_offset_label()

    def _set_idle_state(self):
        self.phase = "idle"
        self.labels['phase'].set_label("Offsets saved! Press Start to recalibrate.")
        self.buttons['start'].set_sensitive(True)
        self.buttons['switch'].set_sensitive(False)
        self.buttons['save'].set_sensitive(False)
        for b in self.nudge_buttons:
            b.set_sensitive(False)

    def _update_offset_label(self):
        self.labels['offset'].set_label(f"Offset: X={self.nudge_x:+.3f}  Y={self.nudge_y:+.3f}")

    def change_step(self, widget, step):
        for s, btn in self.step_buttons.items():
            btn.get_style_context().remove_class("button_active")
        widget.get_style_context().add_class("button_active")
        self.step = step

    def nudge(self, widget, axis, direction):
        dist = direction * self.step
        self._screen._ws.klippy.gcode_script(f"IDEX_VISUAL_NUDGE AXIS={axis} DIST={dist}")
        if axis == "X":
            self.nudge_x += dist
        else:
            self.nudge_y += dist
        self._update_offset_label()

    def reset_nudge(self, widget):
        # Read reference point from Hydra config
        cfg = self._printer.get_config_section(HYDRA_CONFIG)
        ref_x = float(cfg.get("variable_cal_ref_x", "200")) if cfg else 200
        ref_y = float(cfg.get("variable_cal_ref_y", "200")) if cfg else 200
        self._screen._ws.klippy.gcode_script(
            f"G90\nG1 X{ref_x} Y{ref_y} F3000\n"
            "SET_GCODE_VARIABLE MACRO=CALIBRATE_IDEX_XY_VISUAL VARIABLE=nudge_x VALUE=0\n"
            "SET_GCODE_VARIABLE MACRO=CALIBRATE_IDEX_XY_VISUAL VARIABLE=nudge_y VALUE=0"
        )
        self.nudge_x = 0.0
        self.nudge_y = 0.0
        self._update_offset_label()

    def save_offsets(self, widget):
        self._screen._ws.klippy.gcode_script("SAVE_IDEX_XY_VISUAL")
        self._set_idle_state()
        self._update_offset_label()
