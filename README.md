# DroneTune-Notes

Start from a flight-controller configuration that someone else has already
published and flown, then change it based on how **my** quad actually flies, with
the reason for every change recorded.

Two tracks:

- **ArduPilot**: F450 + Pixhawk, indoor optical-flow flight, scripted
  takeoff/hover/land from a Raspberry Pi
- **Betaflight**: 5" FPV quad for obstacle racing

What's in it:

- **Reference configurations**: ArduPilot's published per-airframe parameter files,
  checked against the current ArduCopter release (renamed parameters,
  out-of-range values and unit changes are flagged automatically)
- **Overlay build**: reference file + my small, commented overlay files → one
  `.param` file to load in Mission Planner
- **Explain / compare / diff tools**: every parameter grouped by flight phase
  (takeoff, attitude, altitude hold, position hold, landing, failsafe and so on), with the
  official description, units and range. Betaflight `diff all` dumps compared the
  same way.
- **Build and flight problems**: what goes wrong at each stage, from hardware to
  wiring to software to flight, and how it was fixed: [docs/field-problems.md](docs/field-problems.md)

**Why:** I flew FPV obstacle racing in China, on quads someone else built and
tuned. Starting again in the US, I'm building and tuning my own. Writing a
configuration from scratch is slow and error-prone. Starting from a known-good
reference and changing only what my own flights justify is faster, and leaves a
record of why each value is what it is.

**Maintainer:** Suining Liu

> **Status (v0.1):** tools, reference data and the starting overlays for the F450 are in
> place. The overlays haven't been flight-tested yet, so the change logs are empty.
> Treat every value as a starting point. Always test with props off first.

## Quick start

Python 3.11+, standard library only.

```bash
# ArduPilot: build the parameter file for my F450
python ardupilot/tools/build_params.py ardupilot/my-quad
#   → ardupilot/my-quad/build/final.param, plus a table of every change and why

# explain any parameter file, grouped by flight phase
python ardupilot/tools/classify.py Hexsoon-edu450

# compare the attitude-loop gains of all published quads (min / median / max)
python ardupilot/tools/compare_frames.py --phase 05-attitude-stabilize

# what did AutoTune (or I) change?
python ardupilot/tools/diff_params.py before.param after.param

# Betaflight: compare two CLI `diff all` dumps by section (PID, filters, motors, receiver…)
python betaflight/tools/bf_diff.py start.txt now.txt

# tests
python -m unittest discover -s tests
```

The full step-by-step process is in [docs/tuning-workflow.md](docs/tuning-workflow.md).

## My F450 starting point

| | |
|---|---|
| Reference | `Hexsoon-edu450` (450-class X quad, 3S), the closest published match |
| Hardware planned | F450 frame, 2212 920KV motors, 9450 props, 3S, Pixhawk, ELRS receiver on TELEM1, Raspberry Pi on TELEM2, Matek 3901-L0X optical flow + ToF |
| Overlays | `10-wiring` ports and sensors · `20-indoor-no-gps` EKF sources for optical flow · `30-scripted-flight` speed limits, failsafes, 3S battery |
| Firmware checked against | ArduCopter V4.7.2 |

## Flight phases

ArduCopter has about 5,000 parameters. `ardupilot/data/phase_map.toml` sorts them
by the part of the flight they affect, and marks the few in each phase worth reading first:

| Phase | Key parameters (examples) |
|---|---|
| Frame and motors | `FRAME_CLASS`, `MOT_SPIN_MIN`, `MOT_THST_HOVER` |
| Sensors and state estimation | `EK3_SRC1_*`, `RNGFND1_*`, `FLOW_*` |
| Arming and pre-flight checks | `ARMING_SKIPCHK`, `DISARM_DELAY` |
| Takeoff and climb | `PILOT_SPD_UP`, `PILOT_ACC_Z`, `MOT_SPOOL_TIME` |
| Attitude control | `ATC_RAT_*`, `ATC_ANG_*`, `ATC_ACC_*_MAX` |
| Filters and vibration | `INS_GYRO_FILTER`, `INS_HNTCH_*` |
| Altitude hold | `THR_DZ`, `PILOT_SPD_DN`, `PSC_D_*` |
| Position hold | `LOIT_*`, `PHLD_*`, `PSC_NE_*` |
| Navigation (Guided / Auto / RTL) | `WP_*`, `GUID_*`, `RTL_*` |
| Landing | `LAND_SPD_MS`, `LAND_ALT_LOW_M` |
| Failsafes and battery | `FS_*`, `BATT_*` |
| Radio and modes | `RCMAP_*`, `FLTMODE*`, `RC_OVERRIDE_TIME` |
| Companion computer and telemetry | `SERIALn_*`, `MAV_SYSID`, `LOG_*` |

## Repository layout

```
ardupilot/
  tools/        build_params.py  classify.py  compare_frames.py  diff_params.py  fetch_upstream.py  apparams.py
  data/         phase_map.toml   upstream/ (ArduPilot reference files + parameter docs, GPL-3.0)
  my-quad/      base.txt  10-wiring.param  20-indoor-no-gps.param  30-scripted-flight.param  CHANGELOG.md
betaflight/
  tools/        bf_diff.py
  my-quad/      CHANGELOG.md   (numbered `diff all` dumps go here)
docs/           field-problems.md  tuning-workflow.md
flight-log/     TEMPLATE.md
tests/          test_tools.py  fixtures/ (hand-written example dumps for tests)
```

## License

GPL-3.0-or-later. Includes reference data from the ArduPilot project; see
[NOTICE.md](NOTICE.md).
