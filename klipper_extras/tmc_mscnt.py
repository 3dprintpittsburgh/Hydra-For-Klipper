# Hydra for Klipper - TMC MSCNT Monitor
#
# Exposes the TMC2209 MSCNT (microstep counter) register for step-loss
# detection during high-speed moves.
#
# Usage in printer.cfg:
#   [tmc_mscnt stepper_x]
#
# Gcode commands:
#   SAVE_MSCNT STEPPER=stepper_x   - Snapshot current MSCNT value
#   CHECK_MSCNT STEPPER=stepper_x  - Compare current MSCNT to snapshot
#                                     Sets "matched" in status
#
# Access in macros (after CHECK_MSCNT):
#   printer["tmc_mscnt stepper_x"].matched  -> True/False
#   printer["tmc_mscnt stepper_x"].saved    -> saved value
#   printer["tmc_mscnt stepper_x"].current  -> last checked value
#
# Copyright (C) 2026 Thought Space Designs
# Licensed under GPLv3

# Registry of all instances for command dispatch
_instances = {}


class TMCMscntMonitor:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.stepper_name = config.get_name().split(None, 1)[1]
        self.name = config.get_name()
        self.mcu_tmc = None
        self.fields = None
        self._saved = 0
        self._current = 0
        self._matched = True

        _instances[self.stepper_name] = self

        self.printer.register_event_handler(
            "klippy:connect", self._handle_connect
        )

        # Register commands (only once across all instances)
        gcode = self.printer.lookup_object('gcode')
        for cmd, func, desc in [
            ('SAVE_MSCNT', self.cmd_SAVE_MSCNT,
             "Snapshot TMC MSCNT for step-loss comparison"),
            ('CHECK_MSCNT', self.cmd_CHECK_MSCNT,
             "Compare current MSCNT to saved snapshot"),
            ('READ_MSCNT', self.cmd_READ_MSCNT,
             "Read and display current MSCNT value"),
        ]:
            try:
                gcode.register_command(cmd, func, desc=desc)
            except Exception:
                pass

    def _handle_connect(self):
        for prefix in ['tmc2209 ', 'tmc2208 ', 'tmc2130 ', 'tmc5160 ']:
            tmc = self.printer.lookup_object(
                prefix + self.stepper_name, default=None
            )
            if tmc is not None:
                self.mcu_tmc = tmc.mcu_tmc
                self.fields = tmc.fields
                return
        raise self.printer.config_error(
            "tmc_mscnt: No TMC driver found for '%s'" % self.stepper_name
        )

    def read_mscnt(self):
        if self.mcu_tmc is None:
            return None
        reg_name = self.fields.lookup_register("mscnt", None)
        if reg_name is None:
            return None
        reg_value = self.mcu_tmc.get_register(reg_name)
        return self.fields.get_field("mscnt", reg_value)

    def get_status(self, eventtime=None):
        return {
            'saved': self._saved,
            'current': self._current,
            'matched': self._matched,
            'stepper': self.stepper_name,
        }

    @staticmethod
    def _get_instance(gcmd):
        stepper = gcmd.get('STEPPER', '')
        if stepper in _instances:
            return _instances[stepper]
        if len(_instances) == 1:
            return list(_instances.values())[0]
        gcmd.respond_info("Specify STEPPER= (%s)"
                          % ', '.join(_instances.keys()))
        return None

    def cmd_SAVE_MSCNT(self, gcmd):
        inst = self._get_instance(gcmd)
        if inst is None:
            return
        mscnt = inst.read_mscnt()
        if mscnt is not None:
            inst._saved = mscnt
            inst._matched = True
            gcmd.respond_info(
                "MSCNT %s: saved %d" % (inst.stepper_name, mscnt))

    def cmd_CHECK_MSCNT(self, gcmd):
        inst = self._get_instance(gcmd)
        if inst is None:
            return
        mscnt = inst.read_mscnt()
        if mscnt is not None:
            inst._current = mscnt
            inst._matched = (mscnt == inst._saved)
            if inst._matched:
                gcmd.respond_info(
                    "MSCNT %s: %d == %d (OK)"
                    % (inst.stepper_name, mscnt, inst._saved))
            else:
                gcmd.respond_info(
                    "MSCNT %s: %d != %d (STEP LOSS)"
                    % (inst.stepper_name, mscnt, inst._saved))

    def cmd_READ_MSCNT(self, gcmd):
        inst = self._get_instance(gcmd)
        if inst is None:
            return
        mscnt = inst.read_mscnt()
        if mscnt is not None:
            inst._current = mscnt
            gcmd.respond_info(
                "MSCNT %s: %d/1023" % (inst.stepper_name, mscnt))


def load_config_prefix(config):
    return TMCMscntMonitor(config)
