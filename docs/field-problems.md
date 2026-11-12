# Build and flight problems

These are the problems I've collected and worked through while getting back into
building and tuning my own quads. Each row follows one chain: **the hardware or wiring choice → what the software
shows → what happens in the air → the fix**. Most "software" problems start with a
hardware or wiring decision, so changing a parameter alone doesn't fix them.

**Basis** column:

| Basis | Meaning |
|---|---|
| **Mine** | Found in this project; details in [What I ran into myself](#what-i-ran-into-myself) |
| Docs | Matches the official ArduPilot / PX4 / Betaflight documentation |
| Common | Reported many times by other builders; standard practice |
| Case | A single builder's report. Treat it as a lead to check, not a rule |

US-specific note: VTX power, Remote ID and registration follow FAA / FCC rules.

## A. F450 + Pixhawk (ArduPilot / PX4)

| # | Event | Problem | Cause | Fix | Basis |
|---|---|---|---|---|---|
| A1 | First firmware flash | Pixhawk 2.4.8 shows a **fast red blink** after flashing new PX4 (1.15). Older 1.13.3 boots with a slow blue blink, but ROS 2 work needs the newer one | Many 2.4.8 clones can only use 1 MB of flash; the newest builds for the full-size target don't fit | Flash the build that matches the real flash size. For ArduPilot use `Pixhawk1-1M`. Long term, use a current board (Pixhawk 6C class) | Docs |
| A2 | Receiver hookup | ELRS receiver **burnt** on first power-up | TX→TX / RX→RX wiring | Cross the lines: FC TX → receiver RX, FC RX → receiver TX | Docs |
| A3 | Radio calibration | Receiver is bound (its LED is solid), but Mission Planner's radio page shows **no bars** | The serial port the receiver is on isn't set as RC input. A lit LED only means the receiver is bound to the radio, not that the flight controller is reading it | `SERIALn_PROTOCOL = 23` (RCIN) on that port, then reboot. See `ardupilot/my-quad/10-wiring.param` | Docs |
| A4 | Compass | Calibration keeps failing, or "Compass inconsistency". In Loiter/PosHold the quad **circles ("toilet-bowls")** or the yaw drifts | Compass close to ESCs, power leads or a metal desk; calibrated indoors | Calibrate outdoors away from metal. Move the GPS/compass mast away from power wiring. Large offsets (several hundred or more) point to interference | Docs |
| A5 | First arming | "Motors don't spin" during setup | Slow blue blink = **not armed** (solid = armed). Safety switch not held. Indoors there is no GPS lock, so pre-arm checks fail | Read the pre-arm message in the ground station. Hold the safety switch. For a bench test without GPS, set `GPS1_TYPE = 0` | Docs |
| A6 | Takeoff | **Flips over** the moment it lifts | Motor order, spin direction or prop direction wrong. Wrong frame class/type (mixer) | Run the motor test with props off; check each motor's position and direction against the frame diagram | Docs |
| A7 | Tuning | Hovers fine but **high-frequency shake** in fast flight or at full throttle. Hand-editing PIDs made it shake harder | Vibration (props, loose screws, soft frame) treated as a PID problem | Check vibration in the log first, then filtering (harmonic notch), then PID. Start from the reference values and change one rate-loop gain at a time | Docs |
| A8 | Scripted flight (PX4 Offboard) | Drops out of Offboard mode; first test climbs into the ceiling | Setpoints sent at less than 2 Hz. NED Z axis is **negative up** | Order: connect → send a setpoint → arm → start Offboard → keep streaming. Catch the error and disarm. Order of testing: SITL, then props off, then real flight with a hand on the radio | Docs |
| A9 | Scripted flight (ArduPilot RC override) | Found while reviewing the script: it would overshoot the 0.8 m target, and its final "descent" value of 1485 would not descend | `PILOT_SPD_UP` default (2.5 m/s) is too fast indoors; 1485 is inside the `THR_DZ` deadband around 1500 | Lower `PILOT_SPD_UP`/`PILOT_SPD_DN` (`30-scripted-flight.param`). Use descent PWM below 1500 − `THR_DZ`, or use GUIDED mode instead of RC override | **Mine** |
| A10 | Connecting to the PC | Board powers over USB but **no COM port** appears | Charge-only USB cable or missing driver | Use a data cable and install the driver | Common |
| A11 | Firmware update | Update stops halfway; board won't boot | Weak USB port or hub; no backup of parameters | Save parameters first; use a rear USB port, no hub | Common |
| A12 | Platform choice | F450 on 10" props is slow to respond for control experiments, and crashes are expensive | Large, high-inertia frame | For control-algorithm work, a 5" or a sub-250 g frame is cheaper to crash and quicker to tune | Case |

## What I ran into myself

1. **I couldn't reproduce my old setup.** In China I flew FPV obstacle racing on
   quads someone else built and tuned, and I never learned their configuration.
   Starting again in the US, I had nothing to copy from. That is why this repository
   starts from published reference configurations and records every change.
2. **The published reference files didn't match current firmware.** Checking the
   ArduPilot reference files against ArduCopter 4.7.2 turned up a renamed parameter,
   an out-of-range value and a unit change (table below). I wrote `build_params.py`
   so that these errors stop the build instead of being loaded into the flight controller.
3. **A takeoff/hover/land script would have misbehaved (A9).** While reviewing an
   RC-override flow (PosHold, climb to 0.8 m, hover, step down), I found two problems.
   The default `PILOT_SPD_UP` of 2.5 m/s would overshoot the 0.8 m target indoors.
   The final "descent" value of 1485 µs sits inside the `THR_DZ` deadband around 1500,
   so the quad would never descend. The fixes are in `30-scripted-flight.param`.

### Problems found in the reference parameter files themselves

The files under `ardupilot/data/upstream/frame_params` were written for older
firmware. Checking them against ArduCopter 4.7.2 (run `classify.py` / `build_params.py`):

| File | Problem | What `build_params.py` does |
|---|---|---|
| Hexsoon-edu450 (Copter 4.0) | `ACRO_YAW_P` no longer exists (yaw acro is now `ACRO_Y_RATE` / `ACRO_Y_EXPO`) | Drops it and prints the closest current names |
| Hexsoon-edu450 | `ATC_RAT_YAW_FLTE = 1` is outside the documented range for 4.7.2 | Keeps it and warns; decide in an overlay |
| Old tutorials (4.4 and earlier) | `PILOT_SPEED_UP` in **cm/s** is now `PILOT_SPD_UP` in **m/s**. Copying "50" gives 50 m/s, out of range | Stops the build and suggests `PILOT_SPD_UP` |

## B. 5" FPV quad (Betaflight)

| # | Event | Problem | Cause | Fix | Basis |
|---|---|---|---|---|---|
| B1 | Binding | ELRS receiver **won't bind**; when it does, it drops out in the air | Cold, dull solder joints on the receiver pads; flight vibration breaks them | Re-solder with flux until joints are round and shiny. Bind mode: power-cycle the FC 3 times and leave it on the third time | Common |
| B2 | First arm | **"Death roll"** the instant it arms | Receiver on the wrong UART; radio channel order (AETR) doesn't match Betaflight's map; motor order, prop direction or board orientation wrong | Ports tab: Serial RX on the right UART. Receiver: Serial / CRSF. Match the channel map. Check motors with props off | Docs |
| B3 | First power-up | **New flight controller burnt** | FC and ESC from different brands; the stock FC-to-ESC cable has the **opposite pin order** on some pairings | Check both pinouts and re-pin the cable. Always power up through a smoke stopper first | Case |
| B4 | ESC soldering | Burnt 4-in-1 ESC | Reversed battery leads; solder bridge between motor phases; cold joint on the capacitor; frame screws long enough to puncture the ESC | Multimeter continuity check between pads; check screw length; smoke stopper | Common |
| B5 | Long flight | At about 9 minutes the motors smoke, the ESC burns and the battery is over-discharged | Motor KV too high for the prop (e.g. 2450KV on 8" props) | Match KV to prop size: roughly 2400KV+ for 5–6", ~1400KV for 8", 900–1100KV for 8–10" | Case |
| B6 | After flying | **Hot motors** | Bent props; motor screws touching the windings; bad bearings; filters/PID too aggressive | Fix the mechanical cause first. Then turn on bidirectional DShot (Bluejay/AM32 ESC), set `motor_poles` correctly (usually 14) and enable the RPM filter | Docs |
| B7 | After a prop change | Oscillation; **raising D to stop it made the motors hot** | New props change the inertia the tune was made for; D amplifies noise | Use matched prop sets. Change one thing at a time and log it. Hover 30 s and listen before re-tuning | Case |
| B8 | Video range | Perfect on the bench, **video drops at about 20 m** | VTX powered without an antenna once, which burnt its power amplifier | Never power a VTX without the antenna. Check pit/low-power mode | Common |
| B9 | After a crash | Snowy, stuttering or black video | Cracked antenna; loose video ribbon cable | Check antennas and connectors before blaming the radio; test in another place | Common |
| B10 | Takeoff | Video link drops right after takeoff | VTX overheated while idling on the ground at full power | Don't sit on the ground with the VTX at full power | Case |
| B11 | Behind obstacles | Lost control and video together → crash | Flying behind buildings/trees at long range | Scout the route first; keep line of sight to the antennas | Case |

### Buying and learning

- Simulator first (20–50 h). A good ELRS radio is worth buying, because it carries over to every later quad.
- Spend evenly: an expensive stack on cheap motors is wasted; good motors are better balanced.
- Buy 3–4 batteries, not 10. Batteries puff up when stored fully charged.
- Antenna polarisation must match on the quad and the goggles (LHCP vs RHCP).
- Budget about 30% of the purchase price for repairs, and learn to solder.

## Common checks before every flight

- Solder joints shiny, with no spikes or bridges
- Motor directions match the diagram, and props match the motors
- Radio channels at 100% travel; failsafe tested with props off
- Compass calibrated outdoors (ArduPilot)
- 6+ GPS satellites before any position mode (ArduPilot)
- Battery cells within 0.05 V of each other; don't run LiPos flat
