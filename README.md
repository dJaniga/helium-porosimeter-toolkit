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
use factory values; cells Mini/A/B/C are calibrated daily. The templates
and the worked example below use cell "C" (Vr = 22.2263 cm3).

Calibrate **in the Hassler core holder**, on the same port and plumbing you
measure through. The container is only a means of creating known void
volumes, so the equations are identical to a matrix-cup calibration — but
calibrating in the holder makes `V_D` the dead volume of the circuit you
actually use, and lets the calibration span the same range of `x` as your
measurements.

### 1. Instrument startup

1. Check helium supply; bottle regulator set to **100–105 psi**.
2. Power on and let the instrument warm up for **at least 30 min**; keep the
   ambient temperature stable (±1 °C, away from doors and A/C outlets).
3. Switch to **P.S.** — the display must read **24.00 V**.
4. Switch to **READ** at atmospheric pressure — the display must read **0**
   (adjust with the ZERO potentiometer; if a residual offset remains, record
   it in the `meter_offset` field of the input files).

### 2. Reference-cell calibration (cell "C")

Each configuration obeys `V = Vr·x + V_LIN·x² − V_D` with `x = (R − P) / P`,
where `V` is the void volume in the holder. Three unknowns, so three readings
suffice — but which configurations you pick decides how well `V_LIN` (the
curvature term) is determined, and that is where calibrations go wrong.

**Recommended sequence for cell C — three readings, two removals:**

1. Connect the cell between ports MC-1 and RC (nylon ferrules only).
2. Load the holder **with the full spacer-disc stack** — the most packed
   configuration you can make — and clamp it. This is the `V = 0` reference;
   every later `V` is measured against it.
3. Purge with helium: briefly open SUPPLY, SOURCE, HOLDER, INLET and EXHAUST;
   close INLET, leave EXHAUST open.
4. With SOURCE open (horizontal) and INLET closed: open SUPPLY, set the meter
   to the reference value **R** (19836 for S/N A-20833), close SUPPLY, trim
   with the regulating knob, close SOURCE (vertical). Record **R**.
5. Close EXHAUST, open INLET; after the reading stabilises record the
   pressure for the **full stack**, `V = 0`.
6. Take out a disc of about **a quarter of your total stack volume**
   (10.144 cm³ in the worked example) and repeat steps 3–5.
7. Take out **every remaining disc**, leaving the holder **empty**
   (40.770 cm³ in the example), and repeat steps 3–5. `V` is always the
   *cumulative* void — the sum of everything taken out so far — and you
   never put a disc back mid-sequence.
8. Enter the three `{P, V}` pairs into `calibration_input.json` — this is
   what `init` writes by default — and run:

   ```bash
   python -m porosimeter calibrate examples/calibration_input.json
   ```

9. The program reports `Vr ± u(Vr)`, `V_LIN ± u(V_LIN)` and `V_D`, compared
   against the factory values (cell "C": Vr = 22.2263 cm³,
   V_LIN = 0.155776 cm³). **Any warning means a suspected leak or thermal
   drift — do not measure until resolved.** A steadily falling reading always
   indicates a leak (isolate with INLET/HOLDER, check O-rings and ports
   MC-1/MC-2/RC).

#### Why this sequence, and not the manual's two-disc pair

`V_LIN` is fitted from the curvature across the configurations. Pack them
into a short span of `x` and it is barely determined — which shows up as a
large deviation from the factory value and an alarming-looking warning, even
on a perfectly good calibration. Propagated from 2-count readings on cell C:

| configurations | u(Vr) | u(V_LIN) |
| --- | --- | --- |
| manual pair: 3/8" then 3/4" (max void 20.46 cm³) | 0.14 % | **22 %** |
| **quarter out, then all out — shipped default** | **0.09 %** | **7.8 %** |
| one disc at a time, five points, ending empty | 0.09 % | 8.8 % |

Three well-placed points beat five badly-placed ones: the five-point
sequence spends three of its readings in the low-`x` region, where they add
little leverage while each still carries its own disc-volume uncertainty.
Where the **middle** point sits is what matters, and the optimum is about a
quarter of the way up the span:

| middle point | 3.398 | 6.768 | **10.144** | 13.542 | 20.460 | 34.002 |
| --- | --- | --- | --- | --- | --- | --- |
| u(Vr), cm³ | 0.0346 | 0.0220 | **0.0191** | 0.0192 | 0.0246 | 0.0865 |

The single change that matters is **ending with the holder empty**: it
doubles the span of `x` and cuts u(V_LIN) by roughly a factor of three. It
also brings V_LIN inside the toolkit's 10 % tolerance, so the warning stops
firing on good data.

Two further reasons to empty the holder:

- **It keeps measurements inside the calibrated range.** A 25 cm³ blank gas
  space in the core holder sits at `x ≈ 1.12`. The manual's pair only
  calibrates out to `x ≈ 0.97`, so every measurement extrapolates the
  curvature term. Emptying the holder extends the fit to `x ≈ 1.86` and the
  measurement becomes an interpolation. Because you calibrate on the same
  hardware you can check this directly: your measurement blank (spacer
  discs, no core) should be one of the configurations you calibrated over,
  or lie between two of them.
- **Adding a fourth point turns on the residual check.** With three points
  the fit is exact and the residuals are zero by construction, so a misread
  pressure is invisible. A fourth configuration at `V = 20.460` costs one
  reading, barely moves u(Vr) (0.0191 → 0.0203), and makes a bad point
  visible in the `fit` block.

**If you cannot empty the holder**, put the middle point lower: with a
widest removal of 20.460 cm³, a middle at 6.768 gives u(Vr) = 0.13 % and
u(V_LIN) = 20 %, against 0.14 % and 22 % for a middle at 10.144. It is a
small gain — the span, not the middle, is what limits you.

#### Three different volumes — do not mix them up

| symbol | what it is | set by |
| --- | --- | --- |
| `Vr` | the **reference cell** — the source vessel charged to `R` (cell C = 22.2263 cm³) | which cell you connect |
| `V` | the void on the **receiving** side that the helium expands into | the holder cavity and how much of it the spacer discs occupy |
| `V_D` | the receiving side's dead volume at the `V = 0` configuration | the holder, its lines, and your full spacer stack |

The reference cell never contains discs and is not the holder. The two meet
only through the ratio `x = V / Vr`, and **that ratio is what decides how
well the calibration is conditioned** — it wants to reach about 1.

**The general rule for any cell:** the widest void you can create in the
holder should be at least as big as the reference cell's own volume `Vr`.
Cell C is the best-conditioned cell in the instrument when the holder can be
opened up to 30–40 cm³, and the worst when it cannot — squeezed into 8 cm³
of void it reaches only `x = 0.41` and u(V_LIN) passes 110 %.

#### Choosing the reference cell for your holder

u(Vr) / u(V_LIN), relative, from a three-point calibration at 0, ¼ and full
void:

| holder's widest void | Mini (7.67) | A (10.92) | B (14.70) | C (22.23) |
| --- | --- | --- | --- | --- |
| 8 cm³ | **0.24 % / 16 %** | 0.26 % / 51 % | 0.29 % / 67 % | 0.37 % / 112 % |
| 12 cm³ | **0.16 % / 8 %** | 0.17 % / 25 % | 0.19 % / 32 % | 0.24 % / 53 % |
| 16 cm³ | **0.13 % / 5 %** | 0.13 % / 16 % | 0.15 % / 20 % | 0.18 % / 32 % |
| 25 cm³ | 0.10 % / 3 % | 0.10 % / 9 % | 0.10 % / 10 % | 0.12 % / 15 % |
| 40 cm³ | 0.09 % / 2 % | **0.08 % / 6 %** | 0.08 % / 6 % | 0.09 % / 8 % |

Calibration alone would always favour the smallest cell. The measurement
pulls the other way: at a 45 cm³ gas space, cell C resolves a pore volume to
u(Vp) = 0.031 cm³ where Mini manages only 0.057 cm³. For plug-sized work the
holder has to hold a whole plug's grain volume of gas space anyway — around
22 cm³ for a 1"×2" plug, so 30–45 cm³ with the spacers out — and in that
range **cell C is the right choice on both counts**. A cell C that disagrees
with the factory value is nearly always a span problem, not a cell problem.

Judge the result on **Vr**, which is robust (0.09 % here) and which the 1 %
tolerance is sized for. A wide V_LIN is expected and costs little: even a
100 % error in V_LIN moves the delivered porosity by 0.74 pp, and the
realistic scatter by about 0.16 pp.

One more reason not to read across from the factory `V_LIN`: the factory
constants were determined in a **rigid matrix cup**, while a holder
calibration also sees the **rubber sleeve**, which deforms slightly as the
expansion pressure changes. That pressure-dependent compliance is absorbed
into the fitted `V_LIN`, so a holder-calibrated `V_LIN` is expected to sit
somewhat off the factory number — and it is the *correct* constant for your
circuit, because it is the one your measurements run through. `Vr` is the
cell's own volume and should still land within a few tenths of a percent.

### Input shapes

The `configurations` list above is the general form and the default. Each
entry is a pressure `P` and the total void volume `V` in the holder at that
pressure (0 for the full spacer stack). Three points give an exact fit;
more are least-squares fitted and the result gains a `fit` block:

```json
"fit": { "n_points": 5, "rms_residual_cm3": 0.0005, "max_residual_cm3": 0.0009 }
```

If any point deviates from the fitted curve by more than `fit_residual_pct`
of `Vr` (default 1 %, override in `tolerances`), a warning flags the likely
misread pressure or wrong void volume. **This is the check worth watching** —
it tests the data against itself rather than against a factory constant.

The classic two-disc shape is still accepted for a cell, as the three-point
special case:

```jsonc
{
  "cell": "C",
  "disc_volumes_cm3": {"V0": 0.0, "V1": 10.144, "V2": 20.460},
  "pressures": {"P_DV": 18820.3, "P1": 13148.8, "P2": 10079.5}
}
```

Both shapes may be mixed freely across cells in the same file, one entry per
cell.

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
| `V_p_cm3` | pore volume, cm³ — helium-accessible (connected) pore space |
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