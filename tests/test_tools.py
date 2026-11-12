"""Run with:  python -m unittest discover -s tests"""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "ardupilot" / "tools"))
sys.path.insert(0, str(ROOT / "betaflight" / "tools"))

import apparams  # noqa: E402
import bf_diff  # noqa: E402

FIX = ROOT / "tests" / "fixtures"


def run(*args):
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


class ParamFileTests(unittest.TestCase):
    def test_formats(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.param"
            p.write_text("# note\nATC_RAT_RLL_P,0.12\nPILOT_SPD_UP 0.5  # why\n"
                         "1 1 THR_DZ 100 9\n@readonly\n", encoding="utf-8")
            pf = apparams.parse_param_file(p)
        self.assertEqual(pf.params, {"ATC_RAT_RLL_P": 0.12, "PILOT_SPD_UP": 0.5, "THR_DZ": 100.0})
        self.assertEqual(pf.notes, ["note"])

    def test_phase_longest_match(self):
        pm = apparams.PhaseMap()
        self.assertEqual(pm.classify("PSC_D_VEL_P"), "07-altitude-hold")
        self.assertEqual(pm.classify("PSC_NE_VEL_P"), "08-position-hold")
        self.assertEqual(pm.classify("RC_OVERRIDE_TIME"), "12-radio-modes")
        self.assertEqual(pm.classify("ATC_RAT_RLL_P"), "05-attitude-stabilize")

    def test_key_params_exist(self):
        meta = apparams.load_metadata()
        missing = [k for p in apparams.PhaseMap().phases for k in p.key_params if k not in meta]
        self.assertEqual(missing, [])


class BuildTests(unittest.TestCase):
    def test_my_quad_builds(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "final.param"
            r = run("ardupilot/tools/build_params.py", "ardupilot/my-quad", "--out", str(out))
            self.assertEqual(r.returncode, 0, r.stderr)
            final = apparams.parse_param_file(out).params
        self.assertEqual(final["SERIAL1_PROTOCOL"], 23)
        self.assertEqual(final["ATC_RAT_RLL_P"], 0.17)       # from the base file
        self.assertNotIn("ACRO_YAW_P", final)                 # renamed upstream, dropped

    def test_unknown_name_stops_build(self):
        with tempfile.TemporaryDirectory() as d:
            q = Path(d)
            (q / "base.txt").write_text("Hexsoon-edu450\n")
            (q / "10-x.param").write_text("PILOT_SPEED_UP,50  # old 4.4 name\n")
            r = run("ardupilot/tools/build_params.py", str(q))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PILOT_SPD_UP", r.stderr)              # suggests the current name


class BetaflightTests(unittest.TestCase):
    def test_parse_and_sections(self):
        a = bf_diff.parse_dump(FIX / "bf_a.txt")
        self.assertEqual(a["pid_profile 0: p_roll"], "45")
        self.assertEqual(a["feature: AIRMODE"], "off")
        self.assertEqual(bf_diff.section_of("set: dshot_bidir"), "motors-esc")
        self.assertEqual(bf_diff.section_of("set: rpm_filter_harmonics"), "filters")
        self.assertEqual(bf_diff.section_of("set: serialrx_provider"), "receiver")

    def test_cli(self):
        r = run("betaflight/tools/bf_diff.py", str(FIX / "bf_a.txt"), str(FIX / "bf_b.txt"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("| dshot_bidir | OFF | ON |", r.stdout)


if __name__ == "__main__":
    unittest.main()
