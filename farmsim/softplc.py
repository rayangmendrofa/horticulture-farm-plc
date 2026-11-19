"""Soft-PLC runtime: runs the ST program like the OpenPLC runtime does.

* Cyclic task at the CONFIGURATION interval (50 ms).
* Modbus TCP *server* for HMI/SCADA using OpenPLC's address map:
    %IXa.b -> discrete input a*8+b      %QXa.b -> coil a*8+b
    %IWn   -> input register n          %QWn   -> holding register n
    %MWn   -> holding register 1024+n
* Live mode (``SoftPLC``): Modbus TCP *master* polling the remote-I/O device PLANT,
  mapped the way OpenPLC maps it: DI -> %IX100.0.., coils <- %QX100.0..,
  IR -> %IW100.., HR <- %QW100..  Real time, 1x.
* Fast-forward mode (``FastPLC``): the plant runs in-process with the bench wiring and
  PLC and plant advance together in virtual time, ``speed`` scans per 50 ms task
  (FDS 5.3). Every timer, PI loop and timeout behaves exactly as at 1x.

Because the addresses match, the HMI works unchanged against the real OpenPLC runtime.
"""
from __future__ import annotations

import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from .bench import ST_FILE, Bench
from .modbus import ModbusClient, ModbusImage, ModbusServer
from .plant_server import N_COILS, N_DI, N_HR, N_IR
from .stvm import STMachine

_ADDR = re.compile(r"%([IQM])([XW])(\d+)(?:\.(\d+))?")


def modbus_location(addr: str):
    """Map an IEC address to (table, index) in OpenPLC's Modbus image."""
    m = _ADDR.fullmatch(addr)
    if not m:
        raise ValueError(f"unsupported address {addr}")
    area, size, n, bit = m.group(1), m.group(2), int(m.group(3)), m.group(4)
    if size == "X":
        idx = n * 8 + int(bit)
        return ("di" if area == "I" else "coils"), idx
    if area == "I":
        return "ir", n
    if area == "Q":
        return "hr", n
    return "hr", 1024 + n


@dataclass
class SlaveDevice:
    host: str = "127.0.0.1"
    port: int = 5020
    unit: int = 1
    di: int = N_DI          # discrete inputs 0.. -> %IX100.0..
    ir: int = N_IR          # input registers 0.. -> %IW100..
    coils: int = N_COILS    # coils 0..           <- %QX100.0..
    hr: int = N_HR          # holding registers 0.. <- %QW100..


class SoftPLC:
    def __init__(self, st_file: Path | str = ST_FILE, listen=("0.0.0.0", 5502),
                 device: SlaveDevice | None = None, strict: bool = False):
        self.vm = STMachine(Path(st_file).read_text(encoding="utf-8"), strict=strict)
        self.image = ModbusImage()
        self.server = ModbusServer(self.image, *listen)
        self.port = self.server.port
        self.device = device or SlaveDevice()
        self.client = ModbusClient(self.device.host, self.device.port, self.device.unit, timeout=0.5)
        self.io_ok = False
        self.io_errors = 0
        self.overruns = 0
        self.max_cycle_ms = 0.0
        self.cycle_ms = deque(maxlen=2000)
        self._stop = threading.Event()
        self._thread = None
        self._map = [(name, *modbus_location(addr), addr[1])
                     for addr, name in self.vm.located.items()]

    # -- lifecycle -----------------------------------------------------------------
    def start(self):
        self._to_image(all_areas=True)
        self.server.start()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="softplc")
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.server.stop()
        self.client.close()

    def _loop(self):
        """Fixed-interval task. An *overrun* is a cycle whose execution takes longer than the
        interval; late wake-ups from the OS scheduler are only re-synchronised."""
        period = self.vm.cycle_ms / 1000.0
        nxt = time.perf_counter()
        while not self._stop.is_set():
            t0 = time.perf_counter()
            self.cycle()
            dur = time.perf_counter() - t0
            self.cycle_ms.append(dur * 1000.0)
            self.max_cycle_ms = max(self.max_cycle_ms, dur * 1000.0)
            if dur > period:
                self.overruns += 1
            nxt += period
            delay = nxt - time.perf_counter()
            if delay > 0:
                time.sleep(delay)
            else:
                nxt = time.perf_counter()

    # -- one PLC cycle ---------------------------------------------------------------
    def cycle(self):
        self._poll_inputs()
        with self.image.lock:
            self._from_image()
            self.vm.scan()
            self._to_image()
        self._write_outputs()

    def _poll_inputs(self):
        d, img = self.device, self.image
        try:
            di = self.client.read_discrete_inputs(0, d.di)
            ir = self.client.read_input_registers(0, d.ir)
            self.io_ok = True
        except (ConnectionError, OSError):
            # remote I/O lost: inputs fall back to 0 (OpenPLC "Set to zero", FDS 13):
            # ESTOP_OK = FALSE trips the system
            di, ir = [False] * d.di, [0] * d.ir
            self.io_ok = False
            self.io_errors += 1
        with img.lock:
            img.di[800:800 + d.di] = di
            img.ir[100:100 + d.ir] = ir

    def _write_outputs(self):
        if not self.io_ok:
            return
        d, img = self.device, self.image
        with img.lock:
            coils = img.coils[800:800 + d.coils]
            hr = img.hr[100:100 + d.hr]
        try:
            self.client.write_coils(0, coils)
            self.client.write_registers(0, hr)
        except (ConnectionError, OSError):
            self.io_ok = False
            self.io_errors += 1

    def _from_image(self):
        """Image -> PLC variables: inputs, plus %M/%Q words an HMI may have written."""
        for name, table, idx, area in self._map:
            self.vm[name] = getattr(self.image, table)[idx]

    def _to_image(self, all_areas=False):
        """PLC variables -> image (outputs and memory)."""
        for name, table, idx, area in self._map:
            if area != "I" or all_areas:
                getattr(self.image, table)[idx] = self.vm[name]


class FastPLC(SoftPLC):
    """Fast-forward demo: VM and plant in one process, ``speed`` scans per task cycle.

    ``plant_server`` (passive) still publishes the plant's simulation registers, so the
    HMI's field-simulation panel works the same way as in live mode.
    """

    def __init__(self, plant_server, st_file: Path | str = ST_FILE, listen=("0.0.0.0", 5502),
                 speed: int = 20):
        super().__init__(st_file, listen, SlaveDevice(port=0))
        self.plant_server = plant_server
        self.bench = Bench(vm=self.vm, plant=plant_server.plant)
        self.speed = speed
        self.io_ok = True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.server.stop()

    def cycle(self):
        with self.image.lock:
            self._from_image()                      # HMI writes (commands, setpoints)
            for _ in range(max(1, int(self.speed))):
                self.bench.tick()                   # inputs -> scan -> outputs -> plant step
            self._to_image()
        self.plant_server.sync()

    def _from_image(self):
        """Only %MW (HMI) words: the I/O comes from the in-process plant."""
        for name, table, idx, area in self._map:
            if area == "M":
                self.vm[name] = getattr(self.image, table)[idx]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Soft-PLC: run greenhouse.st like OpenPLC")
    ap.add_argument("--st", default=str(ST_FILE))
    ap.add_argument("--listen", default="0.0.0.0:5502", help="Modbus server for HMI/SCADA")
    ap.add_argument("--io", default="127.0.0.1:5020", help="remote I/O (plant) address")
    ap.add_argument("--strict", action="store_true", help="strict VM (run-time IEC type checks)")
    args = ap.parse_args(argv)
    lh, lp = args.listen.rsplit(":", 1)
    ih, ip = args.io.rsplit(":", 1)
    plc = SoftPLC(args.st, (lh, int(lp)), SlaveDevice(ih, int(ip)), strict=args.strict).start()
    print(f"softplc: {Path(args.st).name}, cycle {plc.vm.cycle_ms} ms, "
          f"Modbus server :{plc.port}, remote I/O {args.io}  (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        plc.stop()
