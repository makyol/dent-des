"""Scientific invariants and behavioral checks for the DentDES experiment."""
import dataclasses
import math
import unittest

from model import (BookingRequest, Clinic, Config, KINDS, PatientInput,
                   generate_inputs, inputs_hash, make_schedule)


def patient(pid=0, kind="routine", treatment=30., offset=0., attends=True):
    return PatientInput(pid, kind, attends, offset, treatment, 3., 8., 3., 9.)


class ModelTests(unittest.TestCase):
    def test_single_patient_analytic_timing_and_occupancy(self):
        c = Clinic([patient()], 0, 0)
        result = c.run()
        row = c.rows[0]
        self.assertEqual(row["arrival"], 15)
        self.assertEqual(row["start"], 18)
        self.assertEqual(row["discharge"], 59)
        self.assertEqual(row["chair_released"], 65)
        self.assertEqual(row["kit_released"], 102)
        self.assertEqual(result["mean_wait"], 3)
        self.assertAlmostEqual(result["util_dentist"], 38/960)
        self.assertAlmostEqual(result["util_assistant"], (38+9+8)/1440)
        self.assertAlmostEqual(result["util_chair"], (38+9)/1920)
        self.assertAlmostEqual(result["util_sterilizer"], 29/480)

    def test_overtime_integrates_across_closing_and_drains(self):
        c = Clinic([patient(treatment=800)], 0, 0)
        result = c.run()
        self.assertEqual(result["completed"], 1)
        self.assertEqual(result["completed_by_close"], 0)
        self.assertEqual(result["overtime"], 349)
        self.assertGreater(c.env.now, 720)
        self.assertAlmostEqual(result["util_dentist"], (480-18)/960)
        self.assertAlmostEqual(result["overtime_dentist_minutes"], 346)

    def test_scheduler_has_only_booking_information(self):
        raw = [patient(0), patient(1,"complex"), patient(2,"restorative")]
        changed = [dataclasses.replace(p, attends=not p.attends,
                   treatment=999., arrival_offset=10.) for p in raw]
        for s in (0, 1):
            a = make_schedule([BookingRequest(p.pid,p.kind) for p in raw], bool(s))
            b = make_schedule([BookingRequest(p.pid,p.kind) for p in changed], bool(s))
            self.assertEqual(a,b)
            self.assertEqual(a[0],15)
            self.assertEqual(a[2],435)
        self.assertNotEqual(make_schedule([BookingRequest(p.pid,p.kind) for p in raw],False),
                            make_schedule([BookingRequest(p.pid,p.kind) for p in raw],True))

    def test_all_requests_have_unique_bounded_appointments(self):
        for n in (1,22,28,34,42):
            inputs = generate_inputs(123,1,1,n)
            for s in (0,1):
                c = Clinic(inputs,s,0)
                self.assertEqual(len(set(c.schedule.values())),n)
                self.assertTrue(all(0 <= c.schedule[p.pid]+p.arrival_offset <= 480 for p in inputs))

    def test_identical_inputs_across_all_policies(self):
        inputs = generate_inputs(123,1,1,42)
        original = inputs_hash(inputs)
        for s,r in ((0,0),(1,0),(0,1),(1,1)):
            c = Clinic(inputs,s,r,Config(kits_per_kind=1))
            result = c.run()
            self.assertEqual(result["input_hash"],original)
            self.assertEqual(result["attended"],sum(p.attends for p in inputs))
            by_id = {p.pid:p for p in inputs}
            for row in c.rows:
                self.assertEqual(row["treatment"],by_id[row["pid"]].treatment)
                self.assertAlmostEqual(row["arrival"]-row["appointment"],by_id[row["pid"]].arrival_offset)

    def test_deterministic_replay_including_trace(self):
        inputs = generate_inputs(123,2,3,34)
        a,b = Clinic(inputs,1,1,trace=True),Clinic(inputs,1,1,trace=True)
        self.assertEqual(a.run(), b.run())
        self.assertEqual(a.events,b.events)
        self.assertEqual(a.rows,b.rows)

    def test_abundant_kits_make_dispatch_policies_identical(self):
        inputs = generate_inputs(18,1,1,42)
        for s in (0,1):
            a,b = Clinic(inputs,s,0,Config(kits_per_kind=50)),Clinic(inputs,s,1,Config(kits_per_kind=50))
            x,y = a.run(), b.run()
            for key in ("mean_wait","overtime","completed_by_close","util_chair"):
                self.assertEqual(x[key],y[key])
            self.assertEqual(y["bypass_events"],0)

    def test_readiness_dispatch_activates_and_respects_bound(self):
        # Compressed appointments with repeated kit requirements create a known HOL queue.
        inputs = [patient(i, "routine" if i % 3 != 2 else "complex", treatment=30.) for i in range(12)]
        a,b = Clinic(inputs,0,0,Config(kits_per_kind=1)),Clinic(inputs,0,1,Config(kits_per_kind=1))
        for c in (a,b):
            c.schedule = {p.pid:15.+p.pid for p in inputs}
        x,y = a.run(),b.run()
        self.assertGreater(y["bypass_events"],0)
        self.assertLessEqual(y["max_bypasses"],2)
        self.assertNotEqual([r["start"] for r in a.rows],[r["start"] for r in b.rows])
        self.assertTrue(all(0 <= row["kit_unavailable_wait"] <= row["start"]-row["registered"]+1e-8 for row in b.rows))

    def test_zero_bypass_bound_matches_fifo(self):
        inputs = generate_inputs(123,1,1,42)
        a,b = Clinic(inputs,0,0,Config(kits_per_kind=1)),Clinic(inputs,0,1,Config(kits_per_kind=1,max_bypasses=0))
        self.assertEqual(a.run()["mean_wait"],b.run()["mean_wait"])

    def test_empty_and_all_no_show_days(self):
        for inputs in ([],[patient(attends=False)]):
            c = Clinic(inputs,0,0)
            result = c.run()
            self.assertEqual(result["completed"],0)
            self.assertTrue(math.isnan(result["mean_wait"]))
            self.assertEqual(result["overtime"],0)

    def test_resource_conservation_under_stress(self):
        for seed in range(8):
            inputs = generate_inputs(seed,1,1,60)
            c = Clinic(inputs,1,1,Config(chairs=2,dentists=1,assistants=1,kits_per_kind=1))
            result = c.run()  # run checks all resource/kit/patient invariants
            self.assertEqual(result["completed"],result["attended"])
            self.assertTrue(all(0 <= result["util_"+key] <= 1 for key in ("chair","dentist","assistant","sterilizer","frontdesk")))


if __name__ == "__main__":
    unittest.main()
