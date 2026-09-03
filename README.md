# helium-porosimeter-toolkit

Python toolkit for the **Corexport Extended Range Helium Porosimeter (HMPoRZ)**.
JSON-driven daily calibration (Vr, V_LIN with factory-value checks) and
core-plug porosity from two Hassler-holder helium expansions — pore volume,
porosity and bulk density — with GUM uncertainty propagation. Includes the
Polish measurement procedure (LaTeX) and lab docs.

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

## Porosity measurement (core plugs)

A plug rarely fills the Hassler holder on its own, so the free length is
taken up with steel spacer discs. The measurement is **two helium
expansions into the same holder with the same discs**:

```
P_DV   blank    the selected spacer discs alone, the core's space left open
P1     sample   the same discs, undisturbed, with the core added
```

Adding the core fills that space with solid while helium re-enters its pore
network, so what the core removes from the gas volume is its solid
framework — the grain volume. The pore volume follows from the plug's bulk
volume:

```
Vg = V(P_DV) − V(P1)          V(P) = Vr·x + V_LIN·x²,  x = (R − P) / P
Vp = V_T − Vg                 φ = Vp / V_T · 100 %
```

Note the direction: the core *takes gas space away*, so **`P1` > `P_DV`**.
A reversed pair gives a negative Vg and is reported as a warning.

### Procedure (per plug)

1. Dry the plug to constant mass (105 °C, or 60 °C / 45 % RH for
   clay-bearing rock — residual water occupies pore space and biases Vp
   low). Weigh it; record `dry_mass_g` if you want the bulk density.
2. Caliper the diameter and length, averaging several readings. This
   matters: **V_T is the largest single term in the uncertainty budget.**
3. Select the spacer discs that leave a gap just big enough to insert the
   plug — big enough, no bigger.
4. Load **the discs alone**, purge, set the meter to **R**, close SOURCE,
   then close EXHAUST and open INLET. Record the stabilised reading as
   **`P_DV`**.
5. Add the core **without disturbing the discs**. Purge and repeat step 4;
   record **`P1`**.
6. Enter both readings and the plug dimensions and run:

```bash
python -m porosimeter measure examples/measurement_input.json
```

### What has to hold

- **The discs must not move between the two readings.** They then cancel
  algebraically and their volumes never enter the arithmetic — no Annex A
  table, no disc-volume uncertainty. This is the whole reason the procedure
  works with a limited disc set.
- **The holder does not need to be packed full.** Leftover space is
  identical in both runs and cancels exactly. Filling only buys
  resolution, and very little of it: going from 8 cm³ to 20 cm³ of
  leftover space moves the reading contribution from 0.023 to 0.056
  porosity points, against 0.12 pp from the caliper. Do not chase a full
  holder with discs.
- **The core's space must be gas-accessible during the blank.** If your
  blank instead packs that space with steel, you are in the matched-blank
  regime — `P1` would come out *below* `P_DV` and Vp would be the
  difference of the readings itself. The sign of the reading change tells
  you which regime the holder is in; this toolkit implements the first.
- **Same thermal state for both readings.** They are compared as volumes:
  1 K of drift between them shifts Vp by 0.08 cm³, some five times the
  reading repeatability. Read the pair back to back.
- **Stabilised means stabilised.** Stopping early leaves `P1` high and
  biases Vp low — 50 counts short costs 3 % of Vp. Use a criterion (e.g.
  under 2 counts of drift over 60 s). A steadily *falling* reading is a
  leak, not slow equilibration. Low-permeability plugs (< 10 mD) can need
  30 min; keep the equilibration time consistent across a series.
- **Record the confining pressure** in `"meta"`. Helium porosity is
  stress-dependent, and the value is not reportable without it.

### Input

```json
{
  "calibration": { "file": "calibration_result.json", "cell": "A" },
  "samples": [
    {
      "sample_id": "S-01",
      "dry_mass_g": 58.12,
      "core_holder": { "P_DV": 6082.5, "P1": 15432.7 },
      "bulk_volume": { "diameter_cm": 2.54, "length_cm": 5.08 }
    }
  ]
}
```

- `core_holder` — **required**; both readings, in meter counts.
- `bulk_volume` — **required**; caliper dimensions as above, or
  `{"value_cm3": 25.7407}` from an independent method (Archimedes, mercury
  displacement) — use that for chipped or out-of-round plugs, where the
  caliper reads high and would bias porosity low. The readings give Vg, so
  without V_T there is no pore volume.
- `dry_mass_g` — optional; used for the bulk density only.

### Results

| key | meaning |
| --- | --- |
| `V_p_cm3` | pore volume, cm³ — effective (connected) porosity at the stated confining stress |
| `V_T_cm3` | bulk volume, cm³ (`V_T_method` says which route produced it) |
| `porosity_pct` | φ = Vp / V_T · 100 % |
| `bulk_density_g_cm3` | dry mass / V_T |

The echoed `core_holder` block keeps the two raw readings, the blank gas
space `V_D_cm3`, and the directly measured `V_g_cm3` — check `V_D` against
the known holder geometry, since a value off by more than a few tenths
means a leak, a bad seat or the wrong cell constants.

Every result carries a standard uncertainty (1σ) propagated from the raw
inputs (meter repeatability, balance, caliper) through the calibration
(including the Vr–V_LIN covariance).

One consequence of measuring porosity this way is worth stating plainly:
Vp is a **small difference of two large numbers** (25.74 − 21.88), so both
input errors are amplified. On the example plug the toolkit reports
`φ = 15.00 ± 0.87 %`, against ± 0.14 % for the same plug measured directly
against a volume-matched steel billet. The dominant term is the caliper
(u(V_T) = 0.21 cm³), not the meter — which is why step 2 is worth the care,
and why an Archimedes bulk volume is the single best upgrade available to
this procedure.

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