# helium-porosimeter-toolkit

Python toolkit for the **Corexport Extended Range Helium Porosimeter (HMPoRZ)**.
JSON-driven daily calibration (Vr, V_LIN with factory-value checks) and
core-plug measurements — pore volume, porosity and bulk density — with GUM
uncertainty propagation. Includes the Polish measurement procedure (LaTeX)
and lab docs.

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
python -m porosimeter init examples             # write example input templates

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

### Multi-point calibration (more than two discs)

The two-disc procedure above is the three-point special case. To calibrate a
cell from **more than three configurations** — for redundancy, or to average
out reading scatter — replace `pressures`/`disc_volumes_cm3` for that cell
with a `configurations` list:

```jsonc
{
  "cell": "C",
  "configurations": [
    {"P": 17831.9, "V": 0.0},     // completely filled cup: void V = 0
    {"P": 15682.2, "V": 3.398},   // P = equilibrium pressure (meter counts)
    {"P": 14010.7, "V": 6.768},   // V = total void volume in the cup (cm³)
    {"P": 12677.5, "V": 10.10},
    {"P": 11572.6, "V": 13.45}
  ]
}
```

Each point obeys `V = Vr·x + V_LIN·x² − V_D` with `x = (R − P) / P`; `V` is the
total void volume in the matrix cup at that pressure (0 for the fully filled
cup, otherwise the removed-disc volume). With three points the fit is exact
and identical to the two-disc solution; with more, `Vr`, `V_LIN` and `V_D` are
least-squares fitted and the result gains a `fit` block:

```json
"fit": { "n_points": 5, "rms_residual_cm3": 0.0005, "max_residual_cm3": 0.0009 }
```

If any point deviates from the fitted curve by more than `fit_residual_pct` of
`Vr` (default 1 %, override in `tolerances`), a warning flags the likely
misread pressure or wrong void volume. Both input shapes may be mixed freely
across cells in the same file.

## Pore-volume measurement

The toolkit measures **one quantity on the sample**: the pore volume of a
core plug, by helium expansion into a Hassler core holder on port MC-2.
Porosity and bulk density follow from it once the plug's bulk volume is
known. Grain volume and loose material (cuttings, ziarna) are deliberately
**not** supported — the matrix cup is used for calibration only.

### Procedure (per plug)

1. Dry and weigh the plug; record `dry_mass_g` (optional, needed only for
   bulk density). Measure its diameter and length with a caliper.
2. Load the **solid steel plug** into the Hassler holder, clamp it and apply
   the confining pressure you will use for the sample.
3. Purge with helium, set the meter to the reference value **R** exactly as
   in the calibration procedure, close SOURCE.
4. Close EXHAUST, open INLET; once the reading stabilises record it as
   **`P_DV`** — the blank. It fixes the dead volume `V_D` of the holder,
   its tubing and the annulus around the plug.
5. Replace the solid plug with the core sample, keeping everything else
   identical (same holder, same confining pressure, same purge sequence).
6. Repeat steps 3–4 and record the reading as **`P1`**.

Expect **`P1` < `P_DV`**: the porous sample offers the helium more space
than the solid plug did, so the gas expands further and settles lower. The
pore volume is the difference of the two expanded volumes,

```
Vp = V(P1) − V(P_DV),   V(P) = Vr·x + V_LIN·x²,   x = (R − P) / P
```

A reversed pair gives a negative Vp and is reported as a warning.

The blank belongs to the holder, not to the sample: read `P_DV` once per
session and reuse it for every plug measured on the same holder at the same
confining pressure, but re-read it after any change of holder, plug size,
tubing or confining pressure, and on each new measurement day — the same
barometric and thermal drift that forces a daily `Vr`/`V_LIN` calibration
moves `V_D` too. Keep both expansions procedurally identical; they are only
comparable if the thermal state is. Low-permeability samples (< 10 mD) may
need up to 30 min to equilibrate — use a stopwatch and keep equilibration
times consistent across a series.

### Input

```json
{
  "calibration": { "file": "calibration_result.json", "cell": "A" },
  "samples": [
    {
      "sample_id": "S-01",
      "dry_mass_g": 58.12,
      "pore_volume": { "P_DV": 11467.4, "P1": 9537.6 },
      "bulk_volume": { "diameter_cm": 2.54, "length_cm": 5.08 }
    }
  ]
}
```

- `pore_volume` — **required**; both readings, in meter counts.
- `bulk_volume` — optional; either caliper dimensions as above, or
  `{"value_cm3": 25.7407}` from an independent method (mercury
  displacement, Archimedes). Without it only Vp is reported, with a warning
  that porosity and bulk density need the plug's total volume.
- `dry_mass_g` — optional; used for the bulk density only.

```bash
python -m porosimeter measure examples/measurement_input.json
```

### Results

| key | meaning |
| --- | --- |
| `V_p_cm3` | pore volume, cm³ |
| `V_T_cm3` | bulk volume, cm³ (`V_T_method` says which route produced it) |
| `porosity_pct` | φ = Vp / V_T · 100 % |
| `bulk_density_g_cm3` | dry mass / V_T |

The echoed `pore_volume` block keeps the two raw readings and the dead
volume `V_D_cm3` — check it against the known holder geometry (≈ 8 cm³ for
the Hassler holder with a solid plug); a `V_D` off by more than a few tenths
means a leak, a bad seat or the wrong cell constants.

Every result carries a standard uncertainty (1σ) propagated from the raw
inputs (meter repeatability, balance, caliper) through the calibration
(including the Vr–V_LIN covariance), e.g. `porosity = 14.99 ± 0.14 %`.
Defaults were verified against a 20 000-trial Monte Carlo simulation;
override them in the `"uncertainties"` block when conditions are worse.

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