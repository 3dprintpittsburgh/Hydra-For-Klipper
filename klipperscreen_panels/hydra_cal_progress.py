import logging
import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
from ks_includes.screen_panel import ScreenPanel


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Calibration"
        super().__init__(screen, title)

        self.labels = {}
        self.poll_timer = None
        self.started = False
        self.check_count = 0

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                      hexpand=True, vexpand=True)

        self.labels['status'] = Gtk.Label()
        self.labels['status'].set_markup("<big><b>XY Calibration in progress...</b></big>")

        self.labels['info'] = Gtk.Label(label="Printing alignment squares")
        self.labels['info'].set_line_wrap(True)

        self.labels['temps'] = Gtk.Label(label="")

        spinner = Gtk.Spinner()
        spinner.start()
        self.spinner = spinner

        stop_btn = self._gtk.Button("cancel", "Stop Calibration", "color2", self.bts)
        stop_btn.connect("clicked", self._on_stop)
        stop_btn.set_size_request(250, 60)

        box.pack_start(spinner, False, False, 10)
        box.pack_start(self.labels['status'], False, False, 5)
        box.pack_start(self.labels['info'], False, False, 5)
        box.pack_start(self.labels['temps'], False, False, 5)
        box.pack_start(stop_btn, False, False, 20)

        self.content.add(box)

    def activate(self):
        self.started = False
        self.check_count = 0
        # Wait 10 seconds before starting to check for completion
        # (gives the macro time to start executing)
        self.poll_timer = GLib.timeout_add_seconds(10, self._start_checking)
        # Update temps every second
        GLib.timeout_add_seconds(1, self._update_temps)

    def deactivate(self):
        if self.poll_timer:
            GLib.source_remove(self.poll_timer)
            self.poll_timer = None

    def _start_checking(self):
        self.started = True
        self.poll_timer = GLib.timeout_add_seconds(3, self._check_complete)
        return False  # Don't repeat this timer

    def _update_temps(self):
        try:
            t0 = self._printer.get_stat("extruder", "temperature") or 0
            t0t = self._printer.get_stat("extruder", "target") or 0
            t1 = self._printer.get_stat("extruder1", "temperature") or 0
            t1t = self._printer.get_stat("extruder1", "target") or 0
            bed = self._printer.get_stat("heater_bed", "temperature") or 0
            bedt = self._printer.get_stat("heater_bed", "target") or 0
            self.labels['temps'].set_label(
                f"T0: {t0:.0f}/{t0t:.0f}°C  T1: {t1:.0f}/{t1t:.0f}°C  Bed: {bed:.0f}/{bedt:.0f}°C"
            )
        except Exception:
            pass
        return True  # Keep updating

    def _check_complete(self):
        if not self.started:
            return True

        self.check_count += 1

        # Check if all heaters are off (calibration turns them off at the end)
        try:
            t0_target = self._printer.get_stat("extruder", "target") or 0
            t1_target = self._printer.get_stat("extruder1", "target") or 0
            bed_target = self._printer.get_stat("heater_bed", "target") or 0

            if t0_target == 0 and t1_target == 0 and bed_target == 0 and self.check_count > 3:
                # All heaters off = calibration macro finished (it turns everything off)
                self.labels['status'].set_markup("<big><b>Calibration complete!</b></big>")
                self.labels['info'].set_label("Returning to alignment panel...")
                self.spinner.stop()
                GLib.timeout_add(2000, self._go_back)
                return False
        except Exception:
            pass

        return True  # Keep polling

    def _go_back(self):
        self._screen._menu_go_back()
        return False

    def _on_stop(self, widget):
        self._screen._ws.klippy.gcode_script("M112")  # Emergency stop
        self.labels['status'].set_markup("<big><b>Calibration stopped</b></big>")
        self.labels['info'].set_label("Emergency stop sent. Restart required.")
        self.spinner.stop()
        if self.poll_timer:
            GLib.source_remove(self.poll_timer)
            self.poll_timer = None
