# Credits

This project builds on open standards, open-source software and public technical literature.

## Own earlier work
- **plc-batch-station** (T-101 batch mixing station, same author). The Structured Text virtual machine (`farmsim/stvm.py`), Modbus TCP stack (`farmsim/modbus.py`), soft-PLC runtime, test-bench pattern, device blocks (`FB_Motor`, `FB_Valve`, `FB_AnalogIn`, `FB_PIControl`) and the STruC++ compile check were carried over from it and extended here (EXP/LN, lean execution mode, fast-forward runtime, feedforward and integration zone in the PI block, `FB_Actuator`). The electrical drawing engine (`tools/drawings/engine.py`), the troubleshooting-trainer pattern and the structure of the commissioning procedure, I/O checkout sheet and report also come from it.

## Software
- **[OpenPLC](https://autonomylogic.com/)** by Thiago Alves and contributors ([OpenPLC_v3](https://github.com/thiagoralves/OpenPLC_v3)). The target runtime. The soft-PLC follows its Modbus address map and remote-device mapping.
- **[STruC++](https://github.com/Autonomy-Logic/STruCpp)** by Autonomy Logic. The OpenPLC v4 Structured Text compiler, used to compile-check the program (FAT OPL-01), locally and in CI via [setup-strucpp](https://github.com/Autonomy-Logic/setup-strucpp).
- **[OpenPLC Runtime v4](https://github.com/Autonomy-Logic/openplc-runtime)** and **[OpenPLC Editor v4](https://autonomylogic.com/products/openplc)** by Autonomy Logic. Target for FAT part B (phase 4).
- **[MatIEC](https://github.com/beremiz/matiec)** (Beremiz project). Its standard-function behaviour (e.g. REAL→INT rounding) is mirrored in the ST VM.
- **[pymodbus](https://github.com/pymodbus-dev/pymodbus)**. Used in the tests to check interoperability of the Modbus TCP implementation.
- **[pytest](https://pytest.org/)**. Test runner.

## Standards and technical references
- IEC 61131-3: programmable controllers, programming languages
- ISA-5.1 (instrument tagging), ISA-101 (HMI design)
- NAMUR NE 43: fault signalling levels for 4–20 mA transmitters
- Modbus Application Protocol Specification V1.1b3 and Modbus Messaging on TCP/IP Implementation Guide V1.0b (Modbus Organization)
- ANSI/ASABE EP406: heating, ventilating and cooling greenhouses (pad-and-fan sizing)
- IEC 60617 (graphical symbols), IEC 81346-2 (reference designations), IEC 60204-1 (electrical equipment of machines), IEC 60445 (conductor colours), ISO 13849-1 (safety-related control parts), IEC 60364-4-41 (protection against electric shock), IEC 61439-1 (panel assemblies), IEC 62443 (zones for industrial network security): conventions and checks in the drawings and the commissioning procedure
- Allen, R. G. et al. (1998), *Crop evapotranspiration*, FAO Irrigation and Drainage Paper 56: saturation vapour pressure equation used for VPD
- Stull, R. (2011), "Wet-bulb temperature from relative humidity and air temperature", *Journal of Applied Meteorology and Climatology* 50: wet-bulb approximation in the pad model
- Radiation-sum irrigation start, drain-percentage steering and two-part (A/B) stock solutions with acid dosing follow common soilless-culture practice as described in the horticultural literature; the carbonate titration in the pH model is textbook water chemistry.

No code, graphics or text from these references was copied. The process, program, simulator and tests were designed for this project.
