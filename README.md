# helium-porosimeter-toolkit

Python toolkit for the **Corexport Extended Range Helium Porosimeter (HMPoRZ)**.
JSON-driven daily calibration (Vr, V_LIN with factory-value checks) and rock
sample measurements — grain/pore volume, porosity and densities for core plugs
and cuttings — with GUM uncertainty propagation. Includes the Polish
measurement procedure (LaTeX) and lab docs.

The instrument determines rock porosity by Boyle's-law isothermal helium
expansion: a known reference-cell volume of helium at pressure `R` is expanded
into the unknown volume, and the equilibrium pressure `P` gives

```
V = -V_D + Vr·x + V_LIN·x²,   x = (R − P) / P
```

All calculations follow the original Corexport operating manual (cat. no. 123)
and were cross-checked against the manufacturer's HP-41 reference program
(manual Annex B).

## Quick start

```bash
python -m porosimeter init examples            # write example input templates
python -m porosimeter init examples --core     # ...preconfigured for core plugs
python -m porosimeter init examples --grains   # ...preconfigured for cuttings/grains

python -m porosimeter calibrate examples/calibration_input.json
python -m porosimeter measure   examples/measurement_input.json
```

After `pip install -e .` the same commands are available through the installed
`porosimeter` console script (e.g. `porosimeter calibrate ...`).

Each command prints a summary and writes `<name>_result.json`. On Windows use
`py -3` if plain `python` is not on `PATH`.

## Daily calibration procedure

Calibration of the system constants **Vr** and **V_LIN** must be performed
**every measurement day** (and after any tubing/holder change), because both
are affected by barometric pressure and temperature. Reference cells #1 and #2
use factory values; cells Mini/A/B/C are calibrated daily.

### 1. Instrument startup

1. Check helium supply; bottle regulator set to **100–105 psi**.
2. Power on and let the instrument warm up for **at least 30 min**; keep the
   ambient temperature stable (±1 °C, away from doors and A/C outlets).
3. Switch to **P.S.** — the display must read **24.00 V**.
4. Switch to **READ** at atmospheric pressure — the display must read **0**
   (adjust with the ZERO potentiometer; if a residual offset remains, record
   it in the `meter_offset` field of the input files).

### 2. Reference-cell calibration (example: cell "A")

1. Connect the cell between ports MC-1 and RC (nylon ferrules only).
2. Place the matrix cup **with all calibration discs** in the holder and
   clamp it (metal-to-metal contact).
3. Purge with helium: briefly open SUPPLY, SOURCE, HOLDER, INLET and EXHAUST;
   close INLET, leave EXHAUST open.
4. With SOURCE open (horizontal) and INLET closed: open SUPPLY, set the meter
   to the reference value **R** (19836 for S/N A-20833), close SUPPLY, trim
   with the regulating knob, close SOURCE (vertical). Record **R**.
5. Close EXHAUST, open INLET; after the reading stabilises record **P_DV**
   (full cup).
6. Remove the smallest disc (1/8", 3.398 cm³ for the 1-1/2" cup set), repeat
   steps 3–5, record **P1**.
7. Put the 1/8" disc back, remove the 1/4" disc (6.768 cm³), repeat steps
   3–5, record **P2**.
8. Enter `R`, `P_DV`, `P1`, `P2` and the removed-disc volumes into
   `calibration_input.json` and run:

   ```bash
   python -m porosimeter calibrate examples/calibration_input.json
   ```

9. The program solves the calibration equation system and reports
   `Vr ± u(Vr)`, `V_LIN ± u(V_LIN)` and `V_D`, compared automatically against
   the factory values (e.g. cell "A": Vr = 10.9175 cm³, V_LIN = 0.061402 cm³).
   **Any warning means a suspected leak or thermal drift — do not measure
   until resolved.** A steadily falling reading always indicates a leak
   (isolate with INLET/HOLDER, check O-rings and ports MC-1/MC-2/RC).

## Measurements

Configure the sample type once per input file (`"sample_type": "core"` or
`"okruchy"`/`"cuttings"`), or per sample:

- **Core plugs**: grain volume (matrix cup: `P_DV` empty cup, `P1` with
  sample), pore volume (Hassler holder on MC-2: `P_DV` with solid plug, `P1`
  with sample) and bulk volume from plug dimensions. Results: Vg, Vp, V_T,
  grain/bulk density and porosity φ = Vp/V_T·100 %.
- **Cuttings / loose grains**: matrix-cup grain volume only → Vg and grain
  density (pore-volume and dimension blocks are ignored with a warning).

Low-permeability samples (< 10 mD) may need up to 30 min to equilibrate —
use a stopwatch and keep equilibration times consistent across a series.

```bash
python -m porosimeter measure examples/measurement_input.json
```

Every result carries a standard uncertainty (1σ) propagated from the raw
inputs (meter repeatability, disc volumes, balance, caliper) through the
calibration (including the Vr–V_LIN covariance), e.g.
`porosity = 14.99 ± 0.14 %`. Defaults reproduce the ±0.5 % grain-volume
accuracy stated by the manufacturer and were verified against a
20 000-trial Monte Carlo simulation; override them in the `"uncertainties"`
block when conditions are worse.

## Traceability

Measurement results reference the calibration file and cell they were
computed with; input and result JSONs archived together form a complete
data-recording card (operator, date, temperature in `"meta"`).

## References

- Corexport / Core Laboratories, *Extended Range Helium Porosimeter (HMPoRZ)
  Operating Manual*, cat. no. 123 (Polish translation, scanned copy in this
  repository).
- *Procedura pomiaru — porozymetr helowy HMPoRZ* (LaTeX source in `tex/`).
- JCGM 100:2008 (GUM) — uncertainty propagation method used in the
  `porosimeter` package.