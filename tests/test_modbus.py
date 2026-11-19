"""Modbus protocol, soft-PLC and communication-failure tests over real TCP sockets (COM)."""
import time

import pytest

from farmsim import tags
from farmsim.modbus import ModbusClient, ModbusError, ModbusImage, ModbusServer
from farmsim.plant import Plant
from farmsim.plant_server import PlantServer
from farmsim.softplc import FastPLC, SlaveDevice, SoftPLC, modbus_location


@pytest.fixture
def server():
    img = ModbusImage()
    srv = ModbusServer(img, "127.0.0.1", 0).start()
    yield img, srv
    srv.stop()


def test_own_client_round_trip(server):
    img, srv = server
    c = ModbusClient("127.0.0.1", srv.port)
    c.write_registers(1024, [1, 2, 65535])
    assert c.read_holding_registers(1024, 3) == [1, 2, 65535]
    c.write_coils(5, [True, False, True])
    assert c.read_coils(5, 3) == [True, False, True]
    img.di[3] = True
    img.ir[7] = 1234
    assert c.read_discrete_inputs(0, 4) == [False, False, False, True]
    assert c.read_input_registers(7, 1) == [1234]
    with pytest.raises(ModbusError) as e:
        c.read_holding_registers(2040, 20)
    assert e.value.code == 2
    c.close()


def test_interop_with_pymodbus(server):
    """A third-party Modbus stack can talk to our server (OpenPLC uses libmodbus)."""
    pymodbus = pytest.importorskip("pymodbus.client")
    img, srv = server
    c = pymodbus.ModbusTcpClient("127.0.0.1", port=srv.port)
    assert c.connect()
    assert not c.write_registers(1034, [250, 580]).isError()
    assert img.hr[1034:1036] == [250, 580]
    img.di[800:803] = [True, False, True]
    assert c.read_discrete_inputs(800, count=3).bits[:3] == [True, False, True]
    c.close()


def test_openplc_address_map():
    assert modbus_location("%IX100.0") == ("di", 800)
    assert modbus_location("%IX103.0") == ("di", 824)
    assert modbus_location("%QX102.5") == ("coils", 821)
    assert modbus_location("%IW115") == ("ir", 115)
    assert modbus_location("%QW102") == ("hr", 102)
    assert modbus_location("%MW139") == ("hr", 1163)


def _status(c):
    regs = c.read_holding_registers(tags.MW_BASE + tags.STATUS_START, len(tags.STATUS_FIELDS))
    return tags.decode_status(regs)


def test_end_to_end_live_plant_softplc():
    """Plant <-Modbus-> soft-PLC <-Modbus-> HMI client, in real time."""
    plant = PlantServer("127.0.0.1", 0, Plant(clock="05:30")).start()
    plc = SoftPLC(listen=("127.0.0.1", 0), device=SlaveDevice("127.0.0.1", plant.port)).start()
    hmi = ModbusClient("127.0.0.1", plc.port)
    try:
        time.sleep(1.5)
        hmi.write_register(tags.MW_BASE + tags.MW_CMD, tags.CMD_BITS["reset"])
        time.sleep(0.5)
        st = _status(hmi)
        assert st["irr_step_name"] == "IDLE" and st["alarm_list"] == []
        assert st["clock_text"] == "05:30" and st["clim_state_name"] == "VENT"
        hmi.write_register(tags.MW_BASE + tags.MW_CMD, tags.CMD_BITS["irrigate_now"])
        time.sleep(1.0)
        st = _status(hmi)
        assert st["irr_step_name"] == "PRE-MIX" and plant.plant.running["p201"]
        with plant.image.lock:
            plant.image.hr[100] = 1                  # fault bit 0: E-stop
        time.sleep(0.5)
        st = _status(hmi)
        assert st["irr_step_name"] == "FAULT" and st["alarm_list"][0]["tag"] == "A00"
        times = sorted(list(plc.cycle_ms)[1:])
        p95 = times[int(0.95 * (len(times) - 1))]
        assert p95 < 25.0, (p95, plc.max_cycle_ms)
        assert plc.io_errors == 0
    finally:
        hmi.close()
        plc.stop()
        plant.stop()


def test_com01_remote_io_loss_trips():
    plant = PlantServer("127.0.0.1", 0, Plant(clock="05:30"))
    plant.server.start()
    plc = SoftPLC(listen=("127.0.0.1", 0), device=SlaveDevice("127.0.0.1", plant.port))
    try:
        for _ in range(50):
            plc.cycle()
            plant.image.coil_write = time.monotonic()
            plant.tick()
        plc.vm["HMI_CMD"] = tags.CMD_BITS["reset"]
        plc.cycle()
        assert plc.io_ok and plc.vm["ST_ACT1"] == 0
        plant.stop()
        for _ in range(5):
            plc.cycle()
        assert not plc.io_ok and plc.vm["step"] == 99
        assert plc.vm["ST_ACT1"] & 0x0001                # ESTOP_OK reads FALSE -> A00
    finally:
        plc.server.stop()
        plc.client.close()


def test_com02_coupler_watchdog_drops_outputs():
    plant = PlantServer("127.0.0.1", 0, Plant(clock="05:30"))
    plant.server.start()
    c = ModbusClient("127.0.0.1", plant.port)
    try:
        coils = [False] * 24
        coils[17] = True                                   # P-531 pad pump
        c.write_coils(0, coils)
        for _ in range(10):
            plant.tick()
        assert plant.plant.running["p531"] and not plant.watchdog_tripped
        plant.image.coil_write -= 1.5                      # no write for 1.5 s
        for _ in range(4):
            plant.tick()
        assert plant.watchdog_tripped and not plant.plant.running["p531"]
        assert c.read_input_registers(42, 1) == [1]        # IR 42: watchdog tripped
    finally:
        c.close()
        plant.stop()


def test_fast_forward_runs_in_virtual_time():
    plant = PlantServer("127.0.0.1", 0, Plant(clock="06:00"), passive=True)
    plc = FastPLC(plant, listen=("127.0.0.1", 0), speed=20)
    plc.server.start()
    c = ModbusClient("127.0.0.1", plc.port)
    try:
        for _ in range(20 * 30):                           # 30 s of tasks = 10 min virtual
            plc.cycle()
        assert plant.plant.clock_min == 6 * 60 + 10
        assert plc.vm.now == 600_000
        plc.cycle()                                        # inputs lag the plant by one scan
        assert _status(c)["clock_text"] == "06:10"
    finally:
        c.close()
        plc.stop()
        plant.stop()


def test_fast_forward_keeps_hmi_writes_made_during_the_scans():
    """The fast-forward runner releases the image lock while it scans. An HMI write that
    lands meanwhile must not be overwritten by the PLC's old value: it reaches the PLC
    on the next cycle."""
    ps = PlantServer("127.0.0.1", 0, Plant(clock="05:00"), passive=True)
    plc = FastPLC(ps, listen=("127.0.0.1", 0), speed=5)
    plc._to_image(all_areas=True)
    sp_ec = tags.MW_BASE + tags.SP["SP_EC"][0]
    tick, n = plc.bench.tick, [0]

    def tick_with_hmi_write():
        n[0] += 1
        if n[0] == 3:
            plc.image.hr[sp_ec] = 300                   # the HMI writes mid-cycle
        tick()

    plc.bench.tick = tick_with_hmi_write
    plc.cycle()
    assert plc.image.hr[sp_ec] == 300 and plc.vm["SP_EC"] == 250
    plc.cycle()
    assert plc.vm["SP_EC"] == 300 and plc.image.hr[sp_ec] == 300
    plc.server.stop()
    ps.server.stop()
