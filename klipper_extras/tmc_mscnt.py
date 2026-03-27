# Hydra for Klipper - TMC MSCNT Monitor
#
# Exposes the TMC2209 MSCNT (microstep counter) register as a readable
# printer object for step-loss detection during high-speed moves.
#
# Usage in printer.cfg:
#   [tmc_mscnt stepper_x]
#   [tmc_mscnt dual_carriage]
#
# Access in macros:
#   printer["tmc_mscnt stepper_x"].mscnt
#
# Gcode commands:
#   READ_MSCNT STEPPER=stepper_x
#   - Reports current MSCNT value
#
# Copyright (C) 2026 Thought Space Designs
# Licensed under GPLv3

class TMCMscntMonitor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.stepper_name = config.get_name().split(None, 1)[1]
        self.name = config.get_name()
        self.mcu_tmc = None
        self.fields = None
        self._last_mscnt = 0

        # Register for connect event to look up TMC object after all loaded
        self.printer.register_event_handler(
            "klippy:connect", self._handle_connect
        )

        # Register gcode command (only once for all instances)
        gcode = self.printer.lookup_object('gcode')
        try:
            gcode.register_command(
                'READ_MSCNT', self.cmd_READ_MSCNT,
                desc="Read TMC MSCNT register for step-loss detection"
            )
        except Exception:
            pass  # Already registered by another instance

    def _handle_connect(self):
        # Find the TMC driver for this stepper
        for prefix in ['tmc2209 ', 'tmc2208 ', 'tmc2130 ', 'tmc5160 ']:
            tmc = self.printer.lookup_object(
                prefix + self.stepper_name, default=None
            )
            if tmc is not None:
                self.mcu_tmc = tmc.mcu_tmc
                self.fields = tmc.fields
                return
        raise self.printer.config_error(
            f"tmc_mscnt: No TMC driver found for '{self.stepper_name}'"
        )

    def read_mscnt(self):
        """Read MSCNT register value (0-1023)."""
        if self.mcu_tmc is None:
            return None
        reg_name = self.fields.lookup_register("mscnt", None)
        if reg_name is None:
            return None
        reg_value = self.mcu_tmc.get_register(reg_name)
        return self.fields.get_field("mscnt", reg_value)

    def get_status(self, eventtime=None):
        return {
            'mscnt': self._last_mscnt,
            'stepper': self.stepper_name,
        }

    def cmd_READ_MSCNT(self, gcmd):
        stepper = gcmd.get('STEPPER', None)
        if stepper and stepper != self.stepper_name:
            # Let the correct instance handle it
            other = self.printer.lookup_object(
                f"tmc_mscnt {stepper}", default=None
            )
            if other is not None:
                other.cmd_READ_MSCNT(gcmd)
            else:
                gcmd.respond_info(f"No tmc_mscnt configured for {stepper}")
            return
        mscnt = self.read_mscnt()
        if mscnt is not None:
            self._last_mscnt = mscnt
            gcmd.respond_info(
                f"MSCNT {self.stepper_name}: {mscnt}/1023"
            )
        else:
            gcmd.respond_info(
                f"MSCNT {self.stepper_name}: unable to read"
            )


def load_config_prefix(config):
    return TMCMscntMonitor(config)
