import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.overworld import (
    CampOverride,
    CampStatus,
    DryRunRoutePlanner,
    HuntPosition,
    HuntSession,
    KuroMapDataProvider,
    LocalMapDataProvider,
    MapCoordinate,
    MobSpawn,
    NormalizedMapCache,
    TravelCostModel,
    TravelMode,
    cluster_spawns,
    format_dry_run_report,
)


def spawn(spawn_id, x, y, *, state_id=1, floor_id="surface", name="Hoochief"):
    return MobSpawn(
        spawn_id=str(spawn_id),
        mob_id="mob-hoochief",
        mob_name=name,
        state_id=state_id,
        floor_id=floor_id,
        coordinate=MapCoordinate(x, y),
    )


class TestOverworldMobHunt(unittest.TestCase):
    def test_nearby_spawns_same_state_and_floor_form_one_camp(self):
        camps = cluster_spawns([spawn("a", 0, 0), spawn("b", 100, 0)], radius=150)

        self.assertEqual(1, len(camps))
        self.assertEqual(2, camps[0].target_count)

    def test_spawns_on_different_floors_cannot_form_one_camp(self):
        camps = cluster_spawns(
            [spawn("surface", 0, 0), spawn("underground", 1, 1, floor_id="underground")],
            radius=150,
        )

        self.assertEqual(2, len(camps))
        self.assertEqual({"surface", "underground"}, {camp.floor_id for camp in camps})

    def test_spawns_with_different_state_ids_cannot_form_one_camp(self):
        camps = cluster_spawns([spawn("one", 0, 0), spawn("two", 1, 1, state_id=2)], radius=150)

        self.assertEqual(2, len(camps))
        self.assertEqual({1, 2}, {camp.state_id for camp in camps})

    def test_camp_override_can_correct_anchor_name_or_availability(self):
        camps = cluster_spawns([spawn("one", 0, 0)])
        override = CampOverride(
            camps[0].camp_id,
            anchor=MapCoordinate(500, 600),
            display_name="camp_override",
        )

        corrected = cluster_spawns([spawn("one", 0, 0)], overrides=[override])[0]

        self.assertEqual(MapCoordinate(500, 600), corrected.anchor)
        self.assertEqual("camp_override", corrected.display_name)

    def test_kuro_data_can_be_imported_into_and_queried_from_normalized_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_path = root / "map_items.db"
            cache_path = root / "normalized.db"
            self._create_kuro_db(source_path)

            source = KuroMapDataProvider(source_path)
            raw = source.query_target_mob_locations("Hoochief")
            self.assertEqual(["spawn-1", "spawn-2"], [item.spawn_id for item in raw])

            cache = NormalizedMapCache(cache_path)
            source.populate_cache(cache)
            local = LocalMapDataProvider(cache)
            underground = local.query_target_mob_locations("mob-hoochief", floor_id="underground")
            self.assertEqual(["spawn-2"], [item.spawn_id for item in underground])

    def test_cleared_camps_are_excluded_from_planning(self):
        first = spawn("first", 0, 0)
        second = spawn("second", 5000, 0)
        camps = cluster_spawns([first, second], radius=100)
        session = HuntSession()
        session.mark_cleared(camps[0].camp_id)

        plan = DryRunRoutePlanner(cluster_radius=100).plan("Hoochief", [first, second], session=session)

        self.assertEqual(1, len(plan.steps))
        self.assertEqual(camps[1].camp_id, plan.steps[0].camp.camp_id)

    def test_nearby_walking_route_wins_over_teleport(self):
        session = HuntSession(
            current_position=HuntPosition(1, "surface", MapCoordinate(0, 0))
        )
        plan = DryRunRoutePlanner(
            cluster_radius=50,
            travel_cost=TravelCostModel(
                walking_speed_units_per_second=100,
                teleport_seconds=34,
                local_sweep_radius=1000,
            ),
        ).plan("Hoochief", [spawn("near", 100, 0)], session=session)

        self.assertEqual(TravelMode.WALK, plan.steps[0].mode)
        self.assertAlmostEqual(1.0, plan.steps[0].estimated_seconds)

    def test_teleport_becomes_preferable_after_local_cluster_is_exhausted(self):
        session = HuntSession(
            current_position=HuntPosition(1, "surface", MapCoordinate(0, 0))
        )
        spawns = [spawn("near", 100, 0), spawn("distant", 5000, 0)]
        plan = DryRunRoutePlanner(
            cluster_radius=50,
            travel_cost=TravelCostModel(
                walking_speed_units_per_second=100,
                teleport_seconds=10,
                local_sweep_radius=1000,
            ),
        ).plan("Hoochief", spawns, session=session)

        self.assertEqual([TravelMode.WALK, TravelMode.TELEPORT], [step.mode for step in plan.steps])

    def test_failed_and_blocked_camps_are_skipped_without_breaking_route(self):
        spawns = [spawn("failed", 0, 0), spawn("blocked", 1000, 0), spawn("usable", 2000, 0)]
        camps = cluster_spawns(spawns, radius=50)
        session = HuntSession()
        session.mark_failed(camps[0].camp_id)
        session.mark_blocked(camps[1].camp_id)

        plan = DryRunRoutePlanner().plan("Hoochief", spawns, session=session)

        self.assertEqual(1, len(plan.steps))
        self.assertEqual("usable", plan.steps[0].camp.spawns[0].spawn_id)
        self.assertEqual(CampStatus.ACTIVE, session.status_for(plan.steps[0].camp.camp_id))

    def test_dry_run_report_contains_expected_summary(self):
        plan = DryRunRoutePlanner().plan("Hoochief", [spawn("one", 0, 0)])

        report = format_dry_run_report("Hoochief", plan)

        self.assertIn("Raw Spawns: 1", report)
        self.assertIn("Generated Camps: 1", report)
        self.assertIn("01 camp_", report)
        self.assertIn("TELEPORT estimated 34.0s target mobs=1", report)

    @staticmethod
    def _create_kuro_db(path):
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE item (id TEXT PRIMARY KEY, name TEXT NOT NULL, icon TEXT);
                CREATE TABLE location (
                    id TEXT PRIMARY KEY, item_id TEXT NOT NULL, state_id INTEGER NOT NULL,
                    floor_id TEXT, x REAL, y REAL, description TEXT
                );
                INSERT INTO item VALUES ('mob-hoochief', 'Hoochief', NULL);
                INSERT INTO location VALUES ('spawn-1', 'mob-hoochief', 1, 'surface', 0, 0, 'one');
                INSERT INTO location VALUES ('spawn-2', 'mob-hoochief', 1, 'underground', 10, 10, 'two');
                INSERT INTO location VALUES ('other', 'other-mob', 1, 'surface', 20, 20, 'other');
                INSERT INTO item VALUES ('other-mob', 'Other Mob', NULL);
                """
            )


if __name__ == "__main__":
    unittest.main()
