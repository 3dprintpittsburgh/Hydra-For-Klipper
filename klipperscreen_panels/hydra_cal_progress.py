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

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10,
                      halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER,
                      hexpand=True, vexpand=True)

        self.labels['status'] = Gtk.Label(label="XY Calibration in progress...")
        self.labels['status'].set_markup("<big><b>XY Calibration in progress...</b></big>")

        self.labels['info'] = Gtk.Label(label="Printing alignment squares")
        self.labels['info'].set_line_wrap(True)

        spinner = Gtk.Spinner()
        spinner.start()

        stop_btn = self._gtk.Button("cancel", "Stop Calibration", "color2", self.bts)
        stop_btn.connect("clicked", self._on_stop)
        stop_btn.set_size_request(250, 60)

        box.pack_start(spinner, False, False, 10)
        box.pack_start(self.labels['status'], False, False, 5)
        box.pack_start(self.labels['info'], False, False, 5)
        box.pack_start(stop_btn, False, False, 20)

        self.content.add(box)

    def activate(self):
        # Poll for macro completion
        self.poll_timer = GLib.timeout_add_seconds(2, self._check_complete)

    def deactivate(self):
        if self.poll_timer:
            GLib.source_remove(self.poll_timer)
            self.poll_timer = None

    def _check_complete(self):
        # Check if printer is idle (macro finished)
        idle = self._printer.get_stat("idle_timeout", "state")
        if idle == "Idle":
            self.labels['status'].set_markup("<big><b>Calibration complete!</b></big>")
            self.labels['info'].set_label("Returning to alignment panel...")
            # Go back after a short delay
            GLib.timeout_add(1500, self._go_back)
            return False  # Stop polling
        return True  # Keep polling

    def _go_back(self):
        self._screen._menu_go_back()
        return False

    def _on_stop(self, widget):
        self._screen._ws.klippy.gcode_script("CANCEL_PRINT")
        self.labels['status'].set_markup("<big><b>Calibration stopped</b></big>")
        self.labels['info'].set_label("Returning...")
        if self.poll_timer:
            GLib.source_remove(self.poll_timer)
            self.poll_timer = None
        GLib.timeout_add(1500, self._go_back)
