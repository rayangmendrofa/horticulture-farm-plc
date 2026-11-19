# GH-1 Tropical Greenhouse - electrical drawings

Revision A, 2026-11-19. A3 landscape, IEC 60617 symbols, IEC 81346 reference designations.

| Sheet | Drawing no. | Title |
|---|---|---|
| 1 / 15 | [GH1-E-00](GH1-E-00.svg) | Cover sheet, index and legend |
| 2 / 15 | [GH1-E-01](GH1-E-01.svg) | Power distribution and 24 V DC |
| 3 / 15 | [GH1-E-02](GH1-E-02.svg) | Pump feeders P-201, P-531, P-541 |
| 4 / 15 | [GH1-E-03](GH1-E-03.svg) | Exhaust fan feeders F-601 ... F-603 |
| 5 / 15 | [GH1-E-04](GH1-E-04.svg) | Vent and shade net drives (reversing) |
| 6 / 15 | [GH1-E-05](GH1-E-05.svg) | Dosing pumps P-311 ... P-313 |
| 7 / 15 | [GH1-E-06](GH1-E-06.svg) | Safety circuit |
| 8 / 15 | [GH1-E-07](GH1-E-07.svg) | Digital inputs -A1.1 / -A1.2 |
| 9 / 15 | [GH1-E-08](GH1-E-08.svg) | Digital outputs -A1.3 / -A1.4 |
| 10 / 15 | [GH1-E-09](GH1-E-09.svg) | Analog inputs -A1.5 / -A1.6 |
| 11 / 15 | [GH1-E-10](GH1-E-10.svg) | Terminal plan -X2 |
| 12 / 15 | [GH1-E-11](GH1-E-11.svg) | Terminal plans -X1, -X3, -X4 and cables |
| 13 / 15 | [GH1-E-12](GH1-E-12.svg) | Panel layout |
| 14 / 15 | [GH1-E-13](GH1-E-13.svg) | Parts list |
| 15 / 15 | [GH1-E-14](GH1-E-14.svg) | Network architecture |

All sheets in one file: [index.html](index.html) (print-ready) and [GH1-electrical.pdf](GH1-electrical.pdf). The I/O loop-check sheet is [../IO_CHECKOUT.md](../IO_CHECKOUT.md).

## Regenerate

```
python tools/drawings/make_drawings.py
```

Standard library only. Devices, feeders, I/O channels and cables are defined once in `tools/drawings/gh1_data.py`. The schematics, the terminal plans (E-10, E-11), the parts list (E-13) and `docs/IO_CHECKOUT.md` are all generated from it, with terminal numbers assigned automatically and cross-references resolved in two passes. The script also checks the I/O against `farmsim/tags.py`. The drawing engine (`engine.py`) comes from the T-101 project. To make the PDF, print `index.html` with headless Chrome or Edge:

```
chrome --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=<abs path>/GH1-electrical.pdf file:///<abs path>/index.html
```

## Conventions

- **Reference designations**: product aspect with prefix `-`, letter codes per IEC 81346-2. Feeders and field devices take the P&ID loop number: `-K201`/`-M201` = P-201, `-Y401` = XV-401, `-B202` = LSL-201.
- **Cross-references**: `/E-08.4` = drawing GH1-E-08, column 4. The output sheet lists for every contactor coil where its contacts are drawn; each contact names its coil's location.
- **Wire numbers**: potentials keep their name (`L1 L2 L3 N PE`, `+24.1`...`+24.5`, `24V-S`, `0V`). Other wires are `<sheet><nn>` (e.g. `705` is drawn on E-07).
- **Terminals**: `-X1` 230/400 V AC, `-X2` 24 V DC digital and safety (1-8 safety, 11-42 inputs, 101-134 outputs), `-X3` analog (3 per loop: +, -, shield), `-X4` outgoing power, `-X0` PE bar.
- **Safety**: both E-stops act through the safety relay `-K0`, which switches the actuator rail `24V-S`. The PLC only monitors it (`ESTOP_OK`).
