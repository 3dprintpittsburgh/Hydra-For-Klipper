import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

HYDRA_CONFIG = "gcode_macro _HYDRA_CONFIG"


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Hydra IDEX"
        super().__init__(screen, title)

        self.active_tool = -1
        self._load_state()

        self.labels = {}

        grid = Gtk.Grid(
            column_homogeneous=True,
            row_homogeneous=False,
            column_spacing=10,
            row_spacing=5,
            halign=Gtk.Align.FILL,
            valign=Gtk.Align.FILL,
            hexpand=True,
            vexpand=True,
        )
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        grid.set_margin_top(5)
        grid.set_margin_bottom(5)

        # Row 0: Status bar
        status_box = Gtk.Box(spacing=20, halign=Gtk.Align.CENTER)
        self.labels['tool'] = Gtk.Label()
        self.labels['offsets'] = Gtk.Label()
        status_box.add(self.labels['tool'])
        status_box.add(self.labels['offsets'])
        self._update_status()
        grid.attach(status_box, 0, 0, 4, 1)

        grid.attach(Gtk.Separator(hexpand=True), 0, 1, 4, 1)

        # Row 2: Tool selection
        btn_t0 = self._gtk.Button("extruder-0", "Select T0", "color4", self.bts)
        btn_t0.connect("clicked", self.select_tool, 0)
        btn_t1 = self._gtk.Button("extruder-1", "Select T1", "color1", self.bts)
        btn_t1.connect("clicked", self.select_tool, 1)
        grid.attach(btn_t0, 0, 2, 2, 1)
        grid.attach(btn_t1, 2, 2, 2, 1)

        # Row 3: Calibration navigation
        btn_z_cal = self._gtk.Button("z-farther", "Z Calibrate", "color3", self.bts)
        btn_z_cal.connect("clicked", self.open_panel, "zcalibrate")
        btn_xy_visual = self._gtk.Button("move", "XY Eyeball", "color3", self.bts)
        btn_xy_visual.connect("clicked", self.open_panel, "hydra_visual_cal")
        btn_xy_align = self._gtk.Button("fine-tune", "XY Fine-Tune", "color3", self.bts)
        btn_xy_align.connect("clicked", self.open_panel, "hydra_align")
        btn_temp = self._gtk.Button("heat-up", "Temperature", "color2", self.bts)
        btn_temp.connect("clicked", self.open_panel, "temperature")

        grid.attach(btn_z_cal, 0, 3, 1, 1)
        grid.attach(btn_xy_visual, 1, 3, 1, 1)
        grid.attach(btn_xy_align, 2, 3, 1, 1)
        grid.attach(btn_temp, 3, 3, 1, 1)

        # Row 4: Quick actions
        btn_xy_test = self._gtk.Button("printer", "Print XY Test", "color3", self.bts)
        btn_xy_test.connect("clicked", self.run_gcode, "CALIBRATE_IDEX_XY_ALIGNMENT")
        btn_home = self._gtk.Button("home", "Home All", "color2", self.bts)
        btn_home.connect("clicked", self.run_gcode, "G28")
        btn_show = self._gtk.Button("info", "Show Offsets", "color1", self.bts)
        btn_show.connect("clicked", self.run_gcode, "SHOW_IDEX_OFFSETS")
        btn_status = self._gtk.Button("console", "Hydra Status", "color1", self.bts)
        btn_status.connect("clicked", self.run_gcode, "HYDRA_STATUS")

        grid.attach(btn_xy_test, 0, 4, 1, 1)
        grid.attach(btn_home, 1, 4, 1, 1)
        grid.attach(btn_show, 2, 4, 1, 1)
        grid.attach(btn_status, 3, 4, 1, 1)

        self.content.add(grid)

    def _load_state(self):
        try:
            toolhead = self._printer.get_stat("toolhead")
            if toolhead:
                self.active_tool = 1 if toolhead.get("extruder") == "extruder1" else 0
        except Exception as e:
            logging.warning(f"Hydra dashboard: Could not load state: {e}")

    def _update_status(self):
        self.labels['tool'].set_markup(f"<b>Active: T{self.active_tool}</b>")
        try:
            # Try runtime stat first, fall back to config
            cfg = self._printer.get_stat(HYDRA_CONFIG)
            if not cfg:
                cfg_section = self._printer.get_config_section(HYDRA_CONFIG)
                if cfg_section:
                    x = float(cfg_section.get("variable_offset_x_t1", "0"))
                    y = float(cfg_section.get("variable_offset_y_t1", "0"))
                    z = float(cfg_section.get("variable_offset_z_t1", "0"))
                    self.labels['offsets'].set_label(f"T1 Offsets  X:{x:+.2f}  Y:{y:+.2f}  Z:{z:+.2f}")
                    return
            if cfg:
                x = float(cfg.get("offset_x_t1", 0))
                y = float(cfg.get("offset_y_t1", 0))
                z = float(cfg.get("offset_z_t1", 0))
                self.labels['offsets'].set_label(f"T1 Offsets  X:{x:+.2f}  Y:{y:+.2f}  Z:{z:+.2f}")
        except Exception:
            self.labels['offsets'].set_label("Offsets: --")

    def activate(self):
        self._load_state()
        self._update_status()

    def process_update(self, action, data):
        if action != "notify_status_update":
            return
        if "toolhead" in data and "extruder" in data["toolhead"]:
            self.active_tool = 1 if data["toolhead"]["extruder"] == "extruder1" else 0
            self._update_status()
        if HYDRA_CONFIG in data:
            self._update_status()

    def select_tool(self, widget, tool):
        self._screen._ws.klippy.gcode_script(f"T{tool}")

    def open_panel(self, widget, panel):
        self.menu_item_clicked(widget, {"panel": panel})

    def run_gcode(self, widget, gcode):
        self._screen._ws.klippy.gcode_script(gcode)
