import csv
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import cv2
import numpy as np

from src.overworld.profile_setup import fit_landmarks, main
from src.overworld.navigation.player_locator import SurfaceProfile


class TestHuntProfileSetup(unittest.TestCase):
    def landmarks(self):
        return [dict(image_x=x, image_y=y, kuro_x=100 + x * 10, kuro_y=-300 + y * 10, role=role)
                for x, y, role in ((10, 10, "fit"), (80, 80, "fit"), (20, 70, "held_out"))]

    def test_uniform_calibration_preserves_independent_holdout(self):
        result = fit_landmarks(self.landmarks(), 1)
        self.assertEqual([100, -300], result["origin"])
        self.assertEqual(10, result["units_per_pixel"])
        self.assertEqual(0, result["held_out_max_error_pixels"])

    def test_bad_holdout_is_rejected_instead_of_refitted(self):
        rows = self.landmarks()
        rows[-1]["kuro_x"] += 20
        with self.assertRaisesRegex(ValueError, "Landmark error"):
            fit_landmarks(rows, 1)

    def test_missing_independent_data_nonfinite_duplicate_and_reflected_inputs_fail(self):
        invalid = []
        rows = self.landmarks(); rows[-1]["role"] = "fit"; invalid.append(rows)
        rows = self.landmarks(); rows[0]["image_x"] = float("nan"); invalid.append(rows)
        rows = self.landmarks(); rows[1] = dict(rows[0]); invalid.append(rows)
        rows = self.landmarks()
        for row in rows:
            row["kuro_x"] *= -1; row["kuro_y"] *= -1
        invalid.append(rows)
        for rows in invalid:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                fit_landmarks(rows, 1)

    def test_draft_checks_database_bounds_and_never_enables_movement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reference, database, landmarks = root / "map.png", root / "map.db", root / "landmarks.csv"
            cv2.imwrite(str(reference), np.zeros((100, 100, 3), np.uint8))
            with closing(sqlite3.connect(database)) as conn:
                conn.executescript("""
                    CREATE TABLE item (id TEXT, name TEXT);
                    CREATE TABLE location (id TEXT, item_id TEXT, state_id INTEGER,
                        floor_id TEXT, x REAL, y REAL, description TEXT);
                    INSERT INTO item VALUES ('mob', 'Target');
                    INSERT INTO location VALUES ('one', 'mob', 8, '', 400, 200, '');
                    INSERT INTO location VALUES ('far', 'mob', 8, '', 40000, 200, '');
                """)
            with landmarks.open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(self.landmarks()[0]))
                writer.writeheader(); writer.writerows(self.landmarks())
            args = ["--reference", str(reference), "--database", str(database), "--landmarks", str(landmarks),
                    "--target", "mob", "--state", "8", "--frame-size", "1920", "1080",
                    "--max-error-pixels", "1", "--stationary-tolerance-pixels", "1"]
            output = root / "profile.json"
            draft = main(args + ["--spawn-id", "one", "--output", str(output)])
            for flag in ("surface_verified", "localization_verified", "navigation_verified"):
                self.assertIs(False, draft[flag])
            with self.assertRaisesRegex(ValueError, "manually verified"):
                SurfaceProfile.load(output)
            draft["surface_verified"] = True
            output.write_text(json.dumps(draft), encoding="utf-8")
            profile = SurfaceProfile.load(output)
            self.assertFalse(profile.localization_verified)
            self.assertEqual(10, profile.units_per_pixel)
            for spawn_id in ("unknown", "far"):
                with self.subTest(spawn_id=spawn_id), self.assertRaises(ValueError):
                    main(args + ["--spawn-id", spawn_id, "--output", str(root / "invalid.json")])
                self.assertFalse((root / "invalid.json").exists())
            before = output.read_bytes()
            with self.assertRaises(SystemExit):
                main(args + ["--spawn-id", "one", "--output", str(output)])
            self.assertEqual(before, output.read_bytes())


if __name__ == "__main__":
    unittest.main()
