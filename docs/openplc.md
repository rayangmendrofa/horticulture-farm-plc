# Running GH-1 on OpenPLC v4 — deployment and FAT part B

```
 virtual plant :5021  ⇄  OpenPLC Runtime v4 (greenhouse.st)  ⇄ :502  web HMI
 (Ubuntu, WSL2)          Modbus master plugin → PLANT            python -m farmsim hmi
                         Modbus server plugin ← HMI, FAT script
```

The same `plc/greenhouse.st` that the soft-PLC and the automated FAT run is compiled by STruC++ and executed by **OpenPLC Runtime v4**. The plant simulator plays the remote I/O device PLANT. The HMI and the part B test script talk to the runtime's Modbus server exactly as they talk to the soft-PLC. The route is the one proven on the T-101 project ([plc-batch-station](https://github.com/rayangmendrofa/plc-batch-station/blob/main/docs/openplc.md)), with a larger I/O image.

## 1. Result

**FAT part B passed 7/7 on 19 Nov 2026.**
- **Setup:** OpenPLC Runtime v4.3.2 in Docker on WSL2 Ubuntu (Windows 11 Home), uploaded with OpenPLC Editor CLI 4.3.5.
- **Plant and test script:** both ran in the same Ubuntu, in real time (1×).
- **Raw output:** [`fat_partb_2026-11-19.json`](fat_partb_2026-11-19.json).

| ID | Test | Expected | Result |
|---|---|---|---|
| OPL-01 | Compile with STruC++ 0.8.0 (`python tools/check_openplc_compile.py`, also in CI) | No errors or warnings; located variables and task match the ST VM | **Pass**: 200 located variables match, 50 ms task |
| OPL-02 | Load on Runtime v4; comms, heartbeat, `%MW` map | Runs at 50 ms; HMI registers backed up to `%MW139`; plant watchdog quiet | **Pass**: heartbeat 20.0 per s, PLC clock = plant clock, `%MW139` readable, coils written every cycle (the plant's 1 s watchdog did not trip) |
| OPL-03 | IRRIGATE NOW with 4 × 10 L shots (IRR-07, FE-01…) | 0→10→20→40→0, every zone, in band while watering, no alarms | **Pass**: zones 1–4 in 168 s, in band after 43 s, while watering \|EC − SP\| ≤ 0.14 mS/cm and \|pH − SP\| ≤ 0.12, 45 L delivered, no alarms |
| OPL-04 | E-stop during SHOT (SAF-01) | Field outputs off at once, A00, step 99; no reset while pressed; no restart after release | **Pass**: field outputs off **98 ms** after the E-stop input opened (includes the 50 ms remote-I/O read and write cycles); RESET refused while pressed; no restart 3 s after release; RESET → IDLE |
| OPL-05 | EC analyser wire break during SHOT (SAF-14b) | A23, step 99, A/B dosing off with the reason shown | **Pass**: A23 and step 99 after 1.11 s (1 s signal-fault delay), P-311 off, interlock word names *EC signal fault or A07*; RESET after repair → IDLE |
| OPL-06 | Vent positioner in CLIM MANUAL (CLI-03) | 3-point step control reaches 37 % ± 2 % over remote I/O; closes to the limit switch | **Pass**: settled in 57 s at 36.6 % (error 0.4 %); 0 % → closed limit ZSC-511 in 43 s; AUTO → VENT |
| OPL-07 | Setpoint clamp and read-back (IRR-15) | The PLC clamps and writes back; HMI sees the value in force | **Pass**: SP_EC 9.00 → 4.00; SP_COOL_T 25.0 → 29.0 (SP_VENT_T + 1.0); defaults restored |
| OPL-08 | Kill the plant (remote I/O) during SHOT (COM-01, FDS 13) | *Set to zero* inputs read as E-stop: trip, outputs off | **Pass**: step 99 with A00 **0.06 s** after the plant went down, all field outputs off; after the plant returned, RESET → IDLE, no alarms |

The same script, run against the soft-PLC over TCP (`--plc 127.0.0.1:5522`), also gives 7/7. Its numbers are within a few percent, except the E-stop time (36 ms): the soft-PLC polls its remote I/O every scan, so it has no separate 50 ms I/O cycle.

What part B adds to the automated FAT:
- the real compiler and runtime execute the program;
- OpenPLC's own Modbus master and server do the I/O, with *Set to zero* on comms loss;
- the `%MW` image is sized correctly (FDS §14 item 1, closed);
- control loops and interlocks work through a real 50 ms remote-I/O cycle, not a direct in-process link.

## 2. Get a runtime

Runtime v4 is a headless Linux service (HTTPS API on 8443, no web page), controlled from OpenPLC Editor v4 or its CLI. On Windows, run it in Docker on WSL2:

```bash
docker run -d --name openplc-runtime --network host --cap-add=SYS_NICE --cap-add=SYS_RESOURCE \
  -v openplc-runtime-data:/var/run/runtime ghcr.io/autonomy-logic/openplc-runtime:latest
```
With `--network host` the Modbus server (502) is on the WSL2 host, and Windows reaches it at `127.0.0.1:502`.

## 3. Build and upload

1. Install OpenPLC Editor v4 (Windows: `OpenPLC.Editor_4.3.5.exe`). Its first start installs the CLI `openplc-cli`.
2. Generate the Editor project from the program, then check and compile it locally (no runtime needed):
   ```bash
   python tools/make_openplc_project.py --plant-port 5021     # writes openplc/GH1_Greenhouse/ (git-ignored)
   openplc-cli inspect image openplc/GH1_Greenhouse --target "OpenPLC Runtime v4"     # "Issues: none"
   openplc-cli compile openplc/GH1_Greenhouse --target "OpenPLC Runtime v4" --clean
   ```
3. Upload. This regenerates the project, then asks for the runtime login (the password hidden; never stored or passed on the command line). Add `-CreateUser` on a brand-new runtime:
   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File tools\openplc_runtime.ps1 upload -PlantPort 5021
   ```
   It ends with `Uploaded "GH1_Greenhouse" … exit code 0: OK`. The runtime compiles the program itself and starts the PLC.

   Alternative: open `openplc/GH1_Greenhouse` in the Editor window (**Open → Local project…**) and upload from there. The window keeps its runtime session.

Uploading replaces whatever program the runtime was running. A runtime runs one program.

## 4. Modbus configuration (generated)

### 4.1 Remote device PLANT (Modbus master), from `plc/plant_io_groups.json`
| Group | FC | Start | Size | IEC locations | On comms loss |
|---|---|---|---|---|---|
| PLANT_DI | 2 read discrete inputs | 0 | 32 | `%IX100.0 … %IX103.7` (25 used) | **Set to zero** |
| PLANT_AI | 4 read input registers | 0 | 16 | `%IW100 … %IW115` | **Set to zero** |
| PLANT_DO | 15 write multiple coils | 0 | 24 | `%QX100.0 … %QX102.7` (22 used) | keep last value |
| PLANT_AO | 16 write multiple registers | 0 | 3 | `%QW100 … %QW102` | keep last value |

50 ms cycle and 500 ms timeout. *Set to zero* is a safety setting: the NC inputs then read as *E-stop pressed* and the PLC trips (FDS §13, OPL-08). The output groups are written every cycle, which keeps the I/O coupler's 1 s watchdog satisfied (OPL-02).

### 4.2 Modbus server (for the HMI)
Port 502. Buffer mapping: `%QW` count 1024 (so `%MW0` = holding register 1024, the map the HMI uses) and **`%MW` count 256**. GH-1 uses `%MW0–139`; with the T-101 template's 64, `%MW64` and above would have no backing (FDS §14 item 1).

## 5. Run the plant, the HMI and FAT part B

The runtime must reach the plant. With the runtime in WSL2 the plant runs in the same Ubuntu, and the part B script starts it itself:

```powershell
wsl -d Ubuntu -u root -- sh -c "cd /mnt/c/<path>/horticulture-farm-plc && python3 tools/fat_openplc.py --plant-port 5021 --json result.json"
```
The script takes about 8 minutes. It sets the plant clock to 10:00, prints one line per test, and exits 0 when all pass. Each test starts from a clean IDLE: AUTO, program disabled so no automatic cycle interferes, alarms reset.

To watch, run the HMI on Windows against the runtime (WSL2 forwards localhost):
```bash
python -m farmsim hmi --plc 127.0.0.1:502 --plant 127.0.0.1:5021 --http 127.0.0.1:8092
```
For a demo without the script, start the plant alone in Ubuntu: `python3 -m farmsim plant --port 5021 --clock 06:00`.

## 6. Notes
- **Login.** The runtime login belongs to the person operating it. The upload script reads it from the keyboard; it is never written to a file or a command line.
- **Real time only.** The runtime runs at 1×, so part B uses 10 L shots. The fast-forward demo exists only in the soft-PLC.
- **Open.** Live variables in the Editor's debugger were checked on T-101 (OPL-07 there), not repeated for GH-1. RETAIN for the setpoint block (FDS §14 item 7) is not yet tried on Runtime v4.
