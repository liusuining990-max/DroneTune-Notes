# Tuning workflow

The idea is simple: **don't write a configuration from scratch.** Start from one
that someone has already published and flown on a similar aircraft, load it, and
change it only when a flight or a log shows a reason. Every change is written down
with that reason.

## ArduPilot (F450 + Pixhawk)

1. **Pick the reference.** Compare the published frames and choose the closest
   one in size, battery and motors:

   ```bash
   python ardupilot/tools/compare_frames.py --list
   python ardupilot/tools/compare_frames.py --phase 01-frame-motors
   python ardupilot/tools/classify.py Hexsoon-edu450       # explain every value, flag renamed ones
   ```

   Put its name in `ardupilot/my-quad/base.txt`.

2. **Write overlays only for what is different about my hardware.** One value per line,
   always with a `# reason`. Overlays are applied in name order:

   | File | What goes in it |
   |---|---|
   | `10-wiring.param` | Serial ports, receiver, sensors: everything decided by the wiring |
   | `20-indoor-no-gps.param` | EKF sources for optical-flow flight |
   | `30-scripted-flight.param` | Speed limits for scripted flight, failsafes, battery |
   | `40-tuning.param` | Values changed after test flights (create it after the first flights) |

3. **Build and load.**

   ```bash
   python ardupilot/tools/build_params.py ardupilot/my-quad
   ```

   This writes `ardupilot/my-quad/build/final.param`. In Mission Planner, go to
   Config → Full Parameter List → Load from file → Write Params, then reboot.
   Calibrations (accelerometer, compass, radio, ESC) are **never** copied from
   another aircraft. Do them on this one.

4. **Fly in this order**, props off until step c:
   a. Motor test: check order and direction.
   b. Radio: check failsafe (turn the transmitter off and confirm the FS action shows).
   c. Stabilize hover at 1 m for 30 s. `MOT_HOVER_LEARN = 2` learns the hover throttle.
   d. AltHold, then PosHold/Loiter.
   e. Look at the log: vibration (`VIBE`), hover throttle, battery sag.
   f. AutoTune (one axis per flight) only after vibration is acceptable.
   g. Scripts: SITL first, then props off, then real flight with a hand on the radio.

5. **Change one thing, fly, record.** Add the value to `40-tuning.param` with the
   reason, add a row to `ardupilot/my-quad/CHANGELOG.md`, and copy
   `flight-log/TEMPLATE.md` for the flight. To see what AutoTune changed:

   ```bash
   python ardupilot/tools/diff_params.py before_autotune.param after_autotune.param
   ```

6. **Firmware updates.** Re-download the reference data for the new version and rebuild.
   Renamed parameters show up as build errors, with the new names suggested:

   ```bash
   python ardupilot/tools/fetch_upstream.py --ref ArduCopter-stable
   python ardupilot/tools/build_params.py ardupilot/my-quad
   ```

## Betaflight (5" FPV)

1. **Start from the stack's stock tune or an official preset** (Configurator → Presets,
   e.g. a 5" tune for your frame). Save the starting point: CLI → `diff all` →
   copy into `betaflight/my-quad/00-start.txt`.
2. **Set up for the hardware:** Ports (receiver UART → Serial RX), Receiver (CRSF),
   Motors (DShot, motor direction, `motor_poles`), Modes (ARM switch), VTX table.
   Save `diff all` as `10-setup.txt`.
3. **Check before tuning:** props off motor test; arm with props off to confirm the
   arm switch; first hover in Angle mode; check motor temperature after 30 s.
4. **Fix the mechanics before touching the PID:** balanced props, tight screws, motor
   temperatures even. Then enable bidirectional DShot + RPM filter if the ESC supports it.
5. **Tune with logs:** one slider or value at a time; record it in a numbered `diff all`
   (`20-…`, `21-…`). Compare any two:

   ```bash
   python betaflight/tools/bf_diff.py betaflight/my-quad/00-start.txt betaflight/my-quad/21-dterm.txt
   ```

6. Note each change in `betaflight/my-quad/CHANGELOG.md`.
