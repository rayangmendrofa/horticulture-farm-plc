"""The virtual plant as a Modbus TCP remote-I/O device (OpenPLC remote device PLANT).

Register map (unit id: any)
  Discrete inputs 0..24   field digital inputs     -> PLC %IX100.0..%IX103.0
  Input registers 0..15   analog inputs + clock    -> PLC %IW100..%IW115
  Coils 0..21             PLC digital outputs      <- PLC %QX100.0..%QX102.5
  Holding registers 0..2  dosing pump speeds       <- PLC %QW100..%QW102

I/O coupler watchdog (FDS 13): if no coil write arrives for 1 s, the coupler drops all
outputs, so the field is safe even when the PLC cannot write.

Simulation-only registers (field-simulation panel / test bench, not part of the real plant)
  HR 100..102  fault injection bits (plant.FAULTS order)
  HR 103       momentary push-buttons: b0 START, b1 STOP, b2 RESET (self-clearing)
  HR 104       weather scenario (0 clear, 1 cloudy, 2 rain, 3 storm)
  HR 105       set the clock: minutes since midnight + 1 (self-clearing, 0 = no change)
  IR 32..43    true values: greenhouse temp x10, RH x10, vent x10, net x10, EC x100,
               pH x100, pump flow L/h, pressure x100, tank level x10, CO2 ppm,
               b0 coupler watchdog tripped, day number
"""
from __future__ import annotations

import threading
import time

from .modbus import ModbusImage, ModbusServer
from .plant import BUTTONS, Plant
from .weather import SCENARIOS

N_DI, N_IR, N_COILS, N_HR = 32, 16, 24, 3
HR_FAULTS, HR_BUTTONS, HR_SCENARIO, HR_CLOCK = 100, 103, 104, 105
IR_TRUTH = 32
WATCHDOG_S = 1.0


class PlantServer:
    """``passive=True``: no own thread or watchdog; the fast-forward runner steps the plant
    and calls ``sync()`` to exchange the simulation registers."""

    def __init__(self, host="0.0.0.0", port=5020, plant: Plant | None = None, dt: float = 0.05,
                 passive: bool = False):
        self.plant = plant or Plant()
        self.image = ModbusImage(coils=64, discrete_inputs=64, holding=128, inputs=64)
        self.image.hr[HR_SCENARIO] = SCENARIOS.index(self.plant.weather.scenario)
        self.server = ModbusServer(self.image, host, port)
        self.port = self.server.port
        self.dt = dt
        self.passive = passive
        self.watchdog_tripped = False
        self._stop = threading.Event()
        self._thread = None
        self.publish()

    def start(self):
        self.server.start()
        if not self.passive:
            self.image.coil_write = time.monotonic()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="plant")
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.server.stop()

    def _loop(self):
        nxt = time.perf_counter()
        while not self._stop.is_set():
            self.tick()
            nxt += self.dt
            delay = nxt - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                nxt = time.perf_counter()

    def tick(self):
        img, p = self.image, self.plant
        with img.lock:
            self.watchdog_tripped = time.monotonic() - img.coil_write > WATCHDOG_S
            if self.watchdog_tripped:
                p.write_outputs([False] * N_COILS, [0] * N_HR)
            else:
                p.write_outputs(img.coils[:N_COILS], img.hr[:N_HR])
        self.sync()
        p.step(self.dt)
        self.publish()

    def sync(self):
        """Simulation registers: faults, buttons, scenario, clock."""
        img, p = self.image, self.plant
        with img.lock:
            p.set_fault_words(img.hr[HR_FAULTS:HR_FAULTS + 3])
            buttons, img.hr[HR_BUTTONS] = img.hr[HR_BUTTONS], 0
            clock, img.hr[HR_CLOCK] = img.hr[HR_CLOCK], 0
            scen = img.hr[HR_SCENARIO]
        for i, name in enumerate(BUTTONS):
            if buttons >> i & 1:
                p.press_button(name)
        if clock:
            m = (clock - 1) % 1440
            p.set_clock(f"{m // 60}:{m % 60}")
        if scen < len(SCENARIOS):
            p.weather.scenario = SCENARIOS[scen]
        self.publish()

    def publish(self):
        img, p = self.image, self.plant
        with img.lock:
            img.di[:N_DI] = p.discrete_inputs()
            img.ir[:N_IR] = p.input_registers()
            truth = [p.t_in * 10, p.rh_in * 10, p.vent_pos * 10, p.net_pos * 10, p.ec_true * 100,
                     p.ph_true * 100, p.q_pump * 1000, p.press * 100, p.level_pct * 10, p.co2,
                     self.watchdog_tripped, p.day]
            img.ir[IR_TRUTH:IR_TRUTH + len(truth)] = [max(0, min(65535, round(v))) for v in truth]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="GH-1 virtual plant (Modbus TCP remote I/O)")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5020)
    ap.add_argument("--clock", default="06:00", help="start time of day, HH:MM")
    ap.add_argument("--scenario", default="clear", choices=SCENARIOS)
    args = ap.parse_args(argv)
    srv = PlantServer(args.host, args.port, Plant(clock=args.clock, scenario=args.scenario)).start()
    print(f"plant: Modbus TCP remote I/O on {args.host}:{srv.port}, clock {args.clock}, "
          f"{args.scenario}  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        srv.stop()
