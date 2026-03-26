import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
from ks_includes.screen_panel import ScreenPanel

HYDRA_CONFIG = "gcode_macro _HYDRA_CONFIG"


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "XY Alignment"
        super().__init__(screen, title)

        self.x_offset = 0.0
        self.y_offset = 0.0
        self.z_offset = 0.0
        self.initial_x = 0.0
        self.initial_y = 0.0
        self.step = 0.1

        self._load_offsets()

        self.labels = {}

        main_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)

        # Left: visualization
        self.drawing_area = Gtk.DrawingArea()
        self.drawing_area.set_hexpand(True)
        self.drawing_area.set_vexpand(True)
        self.drawing_area.connect('draw', self.draw_alignment)

        # Right: compact controls grid
        right = Gtk.Grid(column_spacing=2, row_spacing=2)
        right.set_size_request(185, -1)
        row = 0

        # Row 0: Offset display
        self.labels['x_val'] = Gtk.Label(label=f"X:{self.x_offset:+.2f}")
        self.labels['y_val'] = Gtk.Label(label=f"Y:{self.y_offset:+.2f}")
        right.attach(self.labels['x_val'], 0, row, 1, 1)
        right.attach(self.labels['y_val'], 1, row, 2, 1)
        row += 1

        # Row 1: Step sizes
        self.step_buttons = {}
        for i, s in enumerate([0.05, 0.1, 0.5]):
            btn = self._gtk.Button(None, f"{s}", None, self.bts)
            btn.connect("clicked", self.change_step, s)
            self.step_buttons[s] = btn
            right.attach(btn, i, row, 1, 1)
        self.step_buttons[0.1].get_style_context().add_class("button_active")
        row += 1

        # Row 2: X adjust
        x_minus = self._gtk.Button("arrow-left", None, "color1", self.bts)
        x_minus.connect("clicked", self.adjust, "x", -1)
        x_label = Gtk.Label(label="X")
        x_plus = self._gtk.Button("arrow-right", None, "color4", self.bts)
        x_plus.connect("clicked", self.adjust, "x", 1)
        right.attach(x_minus, 0, row, 1, 1)
        right.attach(x_label, 1, row, 1, 1)
        right.attach(x_plus, 2, row, 1, 1)
        row += 1

        # Row 3: Y adjust
        y_minus = self._gtk.Button("arrow-down", None, "color1", self.bts)
        y_minus.connect("clicked", self.adjust, "y", -1)
        y_label = Gtk.Label(label="Y")
        y_plus = self._gtk.Button("arrow-up", None, "color4", self.bts)
        y_plus.connect("clicked", self.adjust, "y", 1)
        right.attach(y_minus, 0, row, 1, 1)
        right.attach(y_label, 1, row, 1, 1)
        right.attach(y_plus, 2, row, 1, 1)
        row += 1

        # Row 4: Reset / Save / Print Test
        reset_btn = self._gtk.Button("refresh", None, "color2", self.bts)
        reset_btn.connect("clicked", self.reset_offsets)
        save_btn = self._gtk.Button("complete", "Save", "color3", self.bts)
        save_btn.connect("clicked", self.save_offsets)
        test_btn = self._gtk.Button("printer", "Test", "color3", self.bts)
        test_btn.connect("clicked", self.print_test)
        right.attach(reset_btn, 0, row, 1, 1)
        right.attach(save_btn, 1, row, 1, 1)
        right.attach(test_btn, 2, row, 1, 1)
        row += 1

        # Row 5: Status
        self.labels['status'] = Gtk.Label(label="Adjust XY until aligned")
        self.labels['status'].set_line_wrap(True)
        right.attach(self.labels['status'], 0, row, 3, 1)

        main_box.pack_start(self.drawing_area, True, True, 5)
        main_box.pack_start(right, False, False, 5)
        self.content.add(main_box)

    def _load_offsets(self):
        try:
            # Subscribe to Hydra config for live updates
            self._screen._ws.klippy.object_subscription({
                "objects": {HYDRA_CONFIG: None}
            })
            # Try runtime stat first
            stat = self._printer.get_stat(HYDRA_CONFIG)
            if stat:
                self.x_offset = float(stat.get("offset_x_t1", 0.0))
                self.y_offset = float(stat.get("offset_y_t1", 0.0))
                self.z_offset = float(stat.get("offset_z_t1", 0.0))
            else:
                # Fallback: read from config defaults
                cfg = self._printer.get_config_section(HYDRA_CONFIG)
                if cfg:
                    self.x_offset = float(cfg.get("variable_offset_x_t1", "0"))
                    self.y_offset = float(cfg.get("variable_offset_y_t1", "0"))
                    self.z_offset = float(cfg.get("variable_offset_z_t1", "0"))
            self.initial_x = self.x_offset
            self.initial_y = self.y_offset
            logging.info(f"Hydra Align: loaded X={self.x_offset} Y={self.y_offset} Z={self.z_offset}")
        except Exception as e:
            logging.warning(f"Hydra Align: Could not load offsets: {e}")

    def activate(self):
        self._load_offsets()
        self._update_labels()
        self.drawing_area.queue_draw()

    def change_step(self, widget, step):
        for s, btn in self.step_buttons.items():
            btn.get_style_context().remove_class("button_active")
        widget.get_style_context().add_class("button_active")
        self.step = step

    def adjust(self, widget, axis, direction):
        if axis == "x":
            self.x_offset = round(self.x_offset + direction * self.step, 3)
        else:
            self.y_offset = round(self.y_offset + direction * self.step, 3)
        self._update_labels()
        self.drawing_area.queue_draw()

    def reset_offsets(self, widget):
        self.x_offset = self.initial_x
        self.y_offset = self.initial_y
        self._update_labels()
        self.drawing_area.queue_draw()

    def _update_labels(self):
        self.labels['x_val'].set_label(f"X:{self.x_offset:+.2f}")
        self.labels['y_val'].set_label(f"Y:{self.y_offset:+.2f}")

    def save_offsets(self, widget):
        # Apply to runtime + saved variables
        script = (
            f"SET_GCODE_VARIABLE MACRO=_HYDRA_CONFIG VARIABLE=offset_x_t1 VALUE={self.x_offset}\n"
            f"SET_GCODE_VARIABLE MACRO=_HYDRA_CONFIG VARIABLE=offset_y_t1 VALUE={self.y_offset}\n"
            f"SAVE_VARIABLE VARIABLE=hydra_offset_x_t1 VALUE={self.x_offset}\n"
            f"SAVE_VARIABLE VARIABLE=hydra_offset_y_t1 VALUE={self.y_offset}\n"
            f'RESPOND MSG="Hydra: XY offsets saved X={self.x_offset} Y={self.y_offset}"'
        )
        self._screen._ws.klippy.gcode_script(script)

        # Also write to hydra_variables.cfg for persistence across restarts
        self._save_to_config_file({
            "offset_x_t1": self.x_offset,
            "offset_y_t1": self.y_offset
        })

        self.labels['status'].set_label(f"Saved X:{self.x_offset:.2f} Y:{self.y_offset:.2f}")
        self.initial_x = self.x_offset
        self.initial_y = self.y_offset

    def _save_to_config_file(self, values):
        """Write values to hydra_variables.cfg on disk."""
        import os, re
        try:
            filepath = os.path.expanduser("~/printer_data/config/hydra_variables.cfg")
            if not os.path.isfile(filepath):
                return
            with open(filepath, 'r') as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                match = re.match(r'^(variable_(\w+))\s*:', line)
                if match and match.group(2) in values:
                    val = values[match.group(2)]
                    comment = ""
                    if "#" in line:
                        comment = "  " + line[line.index("#"):].strip()
                    if isinstance(val, float):
                        val_str = str(int(val)) if val == int(val) else str(val)
                    else:
                        val_str = str(val)
                    new_lines.append(f"variable_{match.group(2)}: {val_str}{comment}\n")
                else:
                    new_lines.append(line)
            with open(filepath, 'w') as f:
                f.writelines(new_lines)
            logging.info(f"Hydra Align: Saved offsets to {filepath}")
        except Exception as e:
            logging.error(f"Hydra Align: Config save error: {e}")

    def print_test(self, widget):
        self.temp_values = {'t0': 200, 't1': 200, 'bed': 60}

        grid = Gtk.Grid(column_spacing=5, row_spacing=8,
                        halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)

        row = 0
        for key, label_text, default in [
            ('t0', 'T0 Nozzle', 200),
            ('t1', 'T1 Nozzle', 200),
            ('bed', 'Bed', 60),
        ]:
            label = Gtk.Label(label=f"{label_text}:", halign=Gtk.Align.END)
            minus_10 = self._gtk.Button("arrow-left", "-10", "color1", self.bts)
            minus_10.connect("clicked", self._temp_adjust, key, -10)
            minus_5 = self._gtk.Button("arrow-left", "-5", "color1", self.bts)
            minus_5.connect("clicked", self._temp_adjust, key, -5)
            self.labels[f'{key}_temp_val'] = Gtk.Label(label=f"{default}°C")
            self.labels[f'{key}_temp_val'].set_width_chars(6)
            plus_5 = self._gtk.Button("arrow-right", "+5", "color4", self.bts)
            plus_5.connect("clicked", self._temp_adjust, key, 5)
            plus_10 = self._gtk.Button("arrow-right", "+10", "color4", self.bts)
            plus_10.connect("clicked", self._temp_adjust, key, 10)

            grid.attach(label, 0, row, 1, 1)
            grid.attach(minus_10, 1, row, 1, 1)
            grid.attach(minus_5, 2, row, 1, 1)
            grid.attach(self.labels[f'{key}_temp_val'], 3, row, 1, 1)
            grid.attach(plus_5, 4, row, 1, 1)
            grid.attach(plus_10, 5, row, 1, 1)
            row += 1

        buttons = [
            {"name": "Cancel", "response": Gtk.ResponseType.CANCEL, "style": "color2"},
            {"name": "Print", "response": Gtk.ResponseType.OK, "style": "color3"},
        ]
        self._gtk.Dialog("XY Test Temperatures", buttons, grid, self._on_test_dialog_response)

    def _temp_adjust(self, widget, key, amount):
        self.temp_values[key] = max(0, self.temp_values[key] + amount)
        self.labels[f'{key}_temp_val'].set_label(f"{self.temp_values[key]}°C")

    def _on_test_dialog_response(self, dialog, response_id):
        self._gtk.remove_dialog(dialog)
        if response_id == Gtk.ResponseType.OK:
            t0 = self.temp_values['t0']
            t1 = self.temp_values['t1']
            bed = self.temp_values['bed']
            self._screen._ws.klippy.gcode_script(
                f"CALIBRATE_IDEX_XY_ALIGNMENT BED_TEMP={bed} NOZZLE_TEMP={t0} NOZZLE_TEMP_T1={t1}"
            )
            # Navigate to progress screen
            self.menu_item_clicked(None, {"panel": "hydra_cal_progress"})

    def draw_alignment(self, da, ctx):
        width = da.get_allocated_width()
        height = da.get_allocated_height()

        ctx.set_source_rgb(0.12, 0.12, 0.12)
        ctx.rectangle(0, 0, width, height)
        ctx.fill()

        padding = 12
        bed_w, bed_h = 430.0, 350.0
        scale = min((width - padding * 2) / bed_w, (height - padding * 2) / bed_h)

        ox = (width - bed_w * scale) / 2
        oy = (height - bed_h * scale) / 2

        ctx.set_source_rgb(0.25, 0.25, 0.25)
        ctx.set_line_width(1.5)
        ctx.rectangle(ox, oy, bed_w * scale, bed_h * scale)
        ctx.stroke()

        cx = ox + 200 * scale
        cy = oy + (bed_h - 200) * scale

        delta_x = self.x_offset - self.initial_x
        delta_y = self.y_offset - self.initial_y
        x_shift = delta_x * scale
        y_shift = delta_y * scale

        squares = [
            (20, "T1"), (40, "T0"), (60, "T1"),
            (80, "T0"), (100, "T1"), (120, "T0"),
        ]

        for size, tool in squares:
            half = size / 2 * scale
            if tool == "T0":
                ctx.set_source_rgba(0.2, 0.5, 1.0, 0.9)
                sx, sy = cx - half, cy - half
            else:
                ctx.set_source_rgba(1.0, 0.3, 0.2, 0.9)
                sx, sy = cx - half + x_shift, cy - half + y_shift
            ctx.set_line_width(max(1.5, 2 * scale / 2))
            ctx.rectangle(sx, sy, half * 2, half * 2)
            ctx.stroke()

        ctx.set_source_rgba(1, 1, 1, 0.25)
        ctx.set_line_width(1)
        ctx.move_to(cx - 6, cy)
        ctx.line_to(cx + 6, cy)
        ctx.move_to(cx, cy - 6)
        ctx.line_to(cx, cy + 6)
        ctx.stroke()

        fs = max(9, min(11, height / 50))
        ctx.set_font_size(fs)
        ly = oy + bed_h * scale - 22

        ctx.set_source_rgba(0.2, 0.5, 1.0, 0.9)
        ctx.rectangle(ox + 4, ly, 8, 8)
        ctx.fill()
        ctx.set_source_rgb(0.5, 0.5, 0.5)
        ctx.move_to(ox + 15, ly + 7)
        ctx.show_text("T0")

        ctx.set_source_rgba(1.0, 0.3, 0.2, 0.9)
        ctx.rectangle(ox + 4, ly + 11, 8, 8)
        ctx.fill()
        ctx.set_source_rgb(0.5, 0.5, 0.5)
        ctx.move_to(ox + 15, ly + 18)
        ctx.show_text(f"T1 (adj: X{delta_x:+.1f} Y{delta_y:+.1f})")
        ctx.stroke()

        if abs(delta_x) < 0.01 and abs(delta_y) < 0.01:
            ctx.set_source_rgb(0.2, 0.8, 0.2)
            status = "NO ADJUSTMENT"
        else:
            ctx.set_source_rgb(1.0, 0.8, 0.2)
            status = f"adj: X{delta_x:+.2f}  Y{delta_y:+.2f}"
        ctx.set_font_size(fs + 1)
        ctx.move_to(ox + bed_w * scale / 2 - 40, oy - 3)
        ctx.show_text(status)
        ctx.stroke()
