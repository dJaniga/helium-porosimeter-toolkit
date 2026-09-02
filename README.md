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

## Measurements

Configure the sample type once per input file (`"sample_type": "core"` or
`"okruchy"`/`"cuttings"`), or per sample:

- **Core plugs**: grain volume (matrix cup: `P_DV` without the sample, `P1`
  with it), pore volume (Hassler holder on MC-2: `P_DV` with a solid plug,
  `P1` with the sample) and bulk volume from plug dimensions. Results: Vg,
  Vp, V_T, grain/bulk density and porosity φ = Vp/V_T·100 %.
- **Cuttings / loose grains**: matrix-cup grain volume only → Vg and grain
  density (pore-volume and dimension blocks are ignored with a warning).

In both blocks `P_DV` is the **blank** — the expansion into the cup or holder
in exactly the state it will be in for `P1`, but without the sample. It fixes
the dead volume `V_D` that `P1` is measured against; on its own it carries no
sample information. The two blocks run in opposite directions: for grain
volume the sample *takes space away*, so `P1` > `P_DV`; for pore volume the
porous plug *adds* accessible space over the solid one, so `P1` < `P_DV`. A
reversed pair is reported as a "volume is not positive" warning.

Low-permeability samples (< 10 mD) may need up to 30 min to equilibrate —
use a stopwatch and keep equilibration times consistent across a series.

```bash
python -m porosimeter measure examples/measurement_input.json
```

### Gap-filling discs in the matrix cup

A sample rarely fills the matrix cup, and the leftover void costs resolution:
the smaller the volume the helium expands into, the more meter counts a given
grain volume is worth. Calibration discs take up that slack. When they are
used, `P_DV` is read **with the discs in place but without the sample** — not
with an empty cup.

Grain volume is evaluated as

```
Vg = V(P_DV) + V_removed − V(P1),   V(P) = Vr·x + V_LIN·x²,   x = (R − P) / P
```

so everything except the sample must be identical between the two expansions,
and anything that did change goes into `removed_disc_volume_cm3`. That leaves
two correct procedures.

**1. Same disc stack in both runs (recommended).** Choose the stack that
leaves a gap slightly larger than the sample — big enough to insert it, no
bigger. Purge, expand, record `P_DV`. Add the sample *without touching the
discs*, purge, expand, record `P1`. Omit `removed_disc_volume_cm3`:

```json
"grain_volume": { "P_DV": 14525.2, "P1": 18172.4 }
```

The disc volumes cancel algebraically and never enter the arithmetic, so the
result does not depend on the Annex A disc table and carries no disc-volume
uncertainty. The stack is part of the blank, so re-read `P_DV` whenever you
rebuild it.

**2. Full cup as the blank (manual section 3.6.2 step 9).** Record `P_DV`
once with the cup completely filled, then remove disc(s) of known total volume
to make room for the sample and record `P1`:

```json
"grain_volume": { "P_DV": 17872.8, "P1": 13643.4,
                  "removed_disc_volume_cm3": 6.768 }
```

One blank then serves every sample size, at the cost of depending on the
tabulated disc volumes. Both forms are exact and give the same Vg (3.000 cm³
in the two examples above, cell A).

What the discs buy is precision. The same 3 cm³ sample in cell A, with the
default 2-count reading repeatability (pressure contribution only; `u(Vr)` and
`u(V_LIN)` from the calibration add to the figure actually reported):

| void in the blank | `P_DV` → `P1` | u(Vg) from the readings |
| --- | --- | --- |
| 25 cm³ (bare cup) | 6082 → 6628 | 0.0157 cm³ — 0.52 % |
| 10 cm³ | 10378 → 12103 | 0.0050 cm³ — 0.17 % |
| 4 cm³ (discs in) | 14525 → 18172 | 0.0024 cm³ — 0.08 % |

Returns flatten out by roughly 4 cm³ of remaining void, so there is nothing to
gain from packing the cup so tightly that the discs wedge the sample or spoil
the metal-to-metal clamp. Large plugs fill the cup by themselves and need no
discs; samples below 1 cm³ are flagged with a percentage-error warning either
way.

Keep both expansions procedurally identical — same purge sequence, same clamp,
same equilibration time — since `P_DV` and `P1` are only comparable if the
thermal state is. Re-read the blank after any change of cup, holder, disc
stack or tubing, and on the same day as the samples, for the same barometric
and thermal reasons that force a daily `Vr`/`V_LIN` calibration.

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