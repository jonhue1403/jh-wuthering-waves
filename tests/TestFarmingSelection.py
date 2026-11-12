"""Offline-only selection tests. These do not authorize live movement or combat."""

import unittest

from src.automation.farming_selection import (
    CandidateRoute, FarmingCatalog, FarmingReadiness, FarmingTarget,
    ObservedMobDrop, TargetKind, starting_catalog,
)


class TestFarmingSelection(unittest.TestCase):
    def setUp(self):
        self.material = FarmingTarget(TargetKind.MATERIAL, "material-1", "Test Material", aliases=("测试材料",))
        self.mob = FarmingTarget(TargetKind.MOB, "mob-1", "Test Mob")
        self.drop = ObservedMobDrop("material-1", "mob-1", "synthetic-test-evidence")
        self.route = CandidateRoute("mob-1", "route-1", "synthetic-test-route-evidence")

    def catalog(self, *, drops=(), routes=()):
        return FarmingCatalog((self.material, self.mob), tuple(drops), tuple(routes))

    def test_pictured_material_searchable_without_guessing_sources(self):
        catalog = starting_catalog()
        match = catalog.search("  fF mEch ")
        self.assertEqual(["ff-mech-core"], [item.target_id for item in match])
        resolution = catalog.resolve(TargetKind.MATERIAL, "ff-mech-core")
        self.assertEqual(FarmingReadiness.SOURCE_UNRESOLVED, resolution.readiness)
        self.assertEqual((), resolution.candidate_mob_ids)
        self.assertEqual((), resolution.qualified_route_ids)

    def test_search_by_kind_alias_and_unicode(self):
        catalog = self.catalog()
        self.assertEqual((self.material,), catalog.search("测试", kind=TargetKind.MATERIAL))
        self.assertEqual((self.mob,), catalog.search("TEST MOB", kind=TargetKind.MOB))
        self.assertEqual((self.material,), catalog.search("ｍａｔｅｒｉａｌ", kind=TargetKind.MATERIAL))
        self.assertEqual((), catalog.search("material", kind=TargetKind.MOB))

    def test_known_mob_is_not_automatically_farmable(self):
        result = self.catalog().resolve(TargetKind.MOB, "mob-1")
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)
        self.assertEqual(("mob-1",), result.candidate_mob_ids)

    def test_observed_drop_without_route_is_not_ready(self):
        result = self.catalog(drops=(self.drop,)).resolve(TargetKind.MATERIAL, "material-1")
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)
        self.assertEqual(("mob-1",), result.candidate_mob_ids)

    def test_route_metadata_alone_never_enables_farming(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        result = catalog.resolve(TargetKind.MATERIAL, "material-1")
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)
        self.assertEqual((), result.qualified_route_ids)

    def test_explicit_failed_verification_still_blocks(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1", route_is_qualified=lambda _: False
        )
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)

    def test_explicit_current_runtime_verifier_can_release_candidate(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        observed = []
        def qualified(route):
            observed.append(route.route_id)
            return route.route_id == "route-1"
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1", route_is_qualified=qualified
        )
        self.assertEqual(FarmingReadiness.READY, result.readiness)
        self.assertEqual(("route-1",), result.qualified_route_ids)
        self.assertEqual(["route-1"], observed)

    def test_unknown_target_and_invalid_search_limit_rejected(self):
        catalog = self.catalog()
        with self.assertRaises(ValueError):
            catalog.resolve(TargetKind.MATERIAL, "unknown")
        with self.assertRaises(ValueError):
            catalog.search(limit=0)
        with self.assertRaises(ValueError):
            catalog.search(limit=True)

    def test_unknown_mapping_ids_and_duplicate_mapping_rejected(self):
        with self.assertRaises(ValueError):
            self.catalog(drops=(ObservedMobDrop("missing", "mob-1", "evidence"),))
        with self.assertRaises(ValueError):
            self.catalog(drops=(self.drop, self.drop))
        with self.assertRaises(ValueError):
            self.catalog(routes=(CandidateRoute("missing", "route-1", "evidence"),))
        with self.assertRaises(ValueError):
            self.catalog(routes=(self.route, self.route))

    def test_unsubstantiated_evidence_and_empty_alias_rejected(self):
        with self.assertRaises(ValueError):
            ObservedMobDrop("material-1", "mob-1", "")
        with self.assertRaises(ValueError):
            CandidateRoute("mob-1", "route-1", "")
        with self.assertRaises(ValueError):
            FarmingTarget(TargetKind.MOB, "mob-1", "Mob", aliases=("",))

    def test_no_developer_file_paths_are_exposed(self):
        result = self.catalog(drops=(self.drop,), routes=(self.route,)).resolve(
            TargetKind.MATERIAL, "material-1"
        )
        serialized = repr(result)
        for key in ("hunt_profile", "Plan Path", "Route Manifest", "profile.json"):
            self.assertNotIn(key, serialized)


if __name__ == "__main__":
    unittest.main()
