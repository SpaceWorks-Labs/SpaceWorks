"""A SIMULATED shelf pointer for tests (decision 331d): no hardware, no standalone adapter script.

It is the in-repo ``MockAdapter`` loop plus what a real Raspberry Pi or ESP32 pointer must do with the two commands
it serves, so tests can assert on what the pointer would be told to do:

* ``locate.indicate`` ``point``/``light`` -> record the pose, switch the (pretend) laser/LED on, remember the on-time;
* ``locate.indicate`` ``clear`` -> switch everything off, always;
* ``locate.calibrate`` ``aim``/``jog`` -> move the (pretend) head.

It also applies the SAFE defaults a real adapter keeps even if the server mis-sent a value: it never exceeds the
``laser_power_pct`` or ``duration_seconds`` it was handed, and ``tick`` auto-clears when the on-time is over. The
``log`` lines say what a real pointer would do ("points at pan 12.5 / tilt -3 for 15 s").
"""
from tests.adapter_conformance.mock_adapter import MockAdapter

POINTER_CAPABILITIES = ("locate.calibrate", "locate.indicate")


class SimShelfPointer(MockAdapter):
    def __init__(self, client, binding_id=None):
        super().__init__(client, binding_id)
        self.pose, self.on_seconds, self.power_pct, self.log = None, 0, 0, []

    @property
    def lit(self):
        return self.pose is not None

    def execute(self, command):
        name, params = command["command"], command["params"]
        if command["capability"] == "locate.indicate" and name == "indicate":
            if params["mode"] == "clear":
                self.pose, self.on_seconds, self.power_pct = None, 0, 0
                self.log.append("clears: laser and LEDs off")
                return
            self.pose = params["pose"]
            self.on_seconds = params["duration_seconds"]
            self.power_pct = params["pose"].get("laser_power_pct", 100 if "pan_deg" in params["pose"] else 0)
            self.log.append(f"{params['mode']}s {_describe(self.pose)} for {self.on_seconds} s")
        elif command["capability"] == "locate.calibrate":
            self.log.append(f"{name}: {_describe(params.get('pose') or params)}")

    def tick(self, seconds):
        """Time passes; the pointer switches itself off when its on-time is used up (the auto-clear a real one keeps)."""
        if self.lit:
            self.on_seconds -= seconds
            if self.on_seconds <= 0:
                self.pose, self.on_seconds, self.power_pct = None, 0, 0
                self.log.append("auto-clears: on-time over")

    def poll_once(self, outcome="succeeded"):
        command = super().poll_once(outcome)
        if command is not None:
            self.execute(command)
        return command


def _describe(pose):
    return ", ".join(f"{key} {value}" for key, value in pose.items())
