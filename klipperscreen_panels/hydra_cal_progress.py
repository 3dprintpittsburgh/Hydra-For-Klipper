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
        self.temp_timer = None
        self.check_count = 0

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                      hexpand=True, vexpand=True)

        self.labels['status'] = Gtk.Label()
        self.labels['status'].set_markup("<big><b>XY Calibration in progress...</b></big>")

        self.labels['info'] = Gtk.Label(label="Printing alignment squares")
        self.labels['info'].set_line_wrap(True)

        self.labels['temps'] = Gtk.Label(label="")

        self.labels['debug'] = Gtk.Label(label="")
        self.labels['debug'].set_line_wrap(True)

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
        box.pack_start(self.labels['debug'], False, False, 5)
        box.pack_start(stop_btn, False, False, 20)

        self.content.add(box)

    def activate(self):
        self.check_count = 0
        logging.info("HydraCalProgress: Panel activated")
        # Start polling after 15 seconds to let macro begin
        self.poll_timer = GLib.timeout_add_seconds(15, self._start_checking)
        self.temp_timer = GLib.timeout_add_seconds(2, self._update_temps)

    def deactivate(self):
        logging.info("HydraCalProgress: Panel deactivated")
        if self.poll_timer:
            GLib.source_remove(self.poll_timer)
            self.poll_timer = None
        if self.temp_timer:
            GLib.source_remove(self.temp_timer)
            self.temp_timer = None

    def _start_checking(self):
        logging.info("HydraCalProgress: Starting completion checks")
        self.poll_timer = GLib.timeout_add_seconds(5, self._check_complete)
        return False

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
        except Exception as e:
            logging.warning(f"HydraCalProgress: Temp update error: {e}")
        return True

    def _check_complete(self):
        self.check_count += 1

        try:
            idle_state = self._printer.get_stat("idle_timeout", "state")
            t0_target = self._printer.get_stat("extruder", "target") or 0
            t1_target = self._printer.get_stat("extruder1", "target") or 0
            bed_target = self._printer.get_stat("heater_bed", "target") or 0
            printer_state = self._printer.state

            debug_msg = (
                f"Check #{self.check_count}: idle={idle_state} "
                f"state={printer_state} "
                f"targets=T0:{t0_target}/T1:{t1_target}/Bed:{bed_target}"
            )
            logging.info(f"HydraCalProgress: {debug_msg}")
            self.labels['debug'].set_label(debug_msg)

            # Calibration macro turns off all heaters at the end
            # Wait for all targets to be 0 AND printer to be in ready/idle state
            all_heaters_off = (t0_target == 0 and t1_target == 0 and bed_target == 0)
            is_idle = (idle_state == "Idle" or idle_state == "Ready")

            if all_heaters_off and is_idle and self.check_count > 2:
                logging.info("HydraCalProgress: Calibration detected as complete")
                self.labels['status'].set_markup("<big><b>Calibration complete!</b></big>")
                self.labels['info'].set_label("Returning to alignment panel...")
                self.labels['debug'].set_label("")
                self.spinner.stop()
                GLib.timeout_add(2000, self._go_back)
                return False

        except Exception as e:
            logging.error(f"HydraCalProgress: Check error: {e}")
            self.labels['debug'].set_label(f"Error: {e}")

        return True

    def _go_back(self):
        logging.info("HydraCalProgress: Navigating back")
        self._screen._menu_go_back()
        return False

    def _on_stop(self, widget):
        logging.info("HydraCalProgress: Stop pressed")
        self._screen._ws.klippy.gcode_script("M112")
        self.labels['status'].set_markup("<big><b>Calibration stopped</b></big>")
        self.labels['info'].set_label("Emergency stop sent. Restart required.")
        self.labels['debug'].set_label("")
        self.spinner.stop()
        if self.poll_timer:
            GLib.source_remove(self.poll_timer)
            self.poll_timer = None
