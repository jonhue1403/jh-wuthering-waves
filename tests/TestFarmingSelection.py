"""Offline-only selection tests. These do not authorize live movement or combat."""

import unittest

from src.automation.farming_selection import (
    CandidateRoute, DocumentedMobDrop, FarmingCatalog, FarmingReadiness,
    FarmingTarget, ObservedMobDrop, TargetKind, starting_catalog,
)


class TestFarmingSelection(unittest.TestCase):
    def setUp(self):
        self.material = FarmingTarget(TargetKind.MATERIAL, "material-1", "Test Material", aliases=("测试材料",))
        self.mob = FarmingTarget(TargetKind.MOB, "mob-1", "Test Mob")
        self.drop = ObservedMobDrop("material-1", "mob-1", "synthetic-test-evidence")
        self.route = CandidateRoute("mob-1", "route-1", "synthetic-test-route-evidence")

    def catalog(self, *, drops=(), routes=(), documented=()):
        return FarmingCatalog(
            (self.material, self.mob), tuple(drops), tuple(routes),
            documented_drops=tuple(documented),
        )

    def test_pictured_material_searchable_without_guessing_sources(self):
        catalog = starting_catalog()
        match = catalog.search("  fF mEch ")
        self.assertEqual(["ff-mech-core"], [item.target_id for item in match])
        resolution = catalog.resolve(TargetKind.MATERIAL, "ff-mech-core")
        self.assertEqual(FarmingReadiness.SOURCE_DOCUMENTED, resolution.readiness)
        self.assertEqual((), resolution.candidate_mob_ids)
        self.assertEqual((), resolution.qualified_route_ids)
        self.assertEqual(5, len(resolution.documented_mob_ids))
        self.assertEqual(
            {"geospider-s4", "sabercat-reaver", "spacetrek-explorer",
             "twin-nova-collapsar-blade", "twin-nova-nebulous-cannon"},
            set(resolution.documented_mob_ids),
        )
        self.assertEqual(5, len(catalog.documented_sources("ff-mech-core")))
        self.assertEqual(
            ["geospider-s4"],
            [item.target_id for item in catalog.search("geospider", kind=TargetKind.MOB)],
        )

    def test_all_27_screenshot_materials_are_searchable_without_routes(self):
        # Independent transcription of the uploaded material grid.
        names = (
            "Premium Tuner", "Premium Sealed Tube", "Premium Resonance Potion",
            "Heterized Metallic Drip", "Mysterious Code", "FF Whisperin Core",
            "FF Howler Core", "Tailored Ring", "Mask of Insanity",
            "Flawless Phlogiston", "Presto Helix", "Waveworn Residue 239",
            "Cadence Blossom", "Premium Energy Core", "FF Tidal Residuum",
            "FF Polygon Core", "Echo Modifier", "FF Exoswarm Core",
            "Reverb Combustor", "FF Mech Core", "Intact Exoswarm Pendant",
            "Layered Wing Polarizer", "Melodic String", "FF Carved Crystal",
            "FF Waveworn Shard", "Transducer", "FF Autopuppet Kernel",
        )
        catalog = starting_catalog()
        material_items = catalog.search(kind=TargetKind.MATERIAL, limit=100)
        self.assertEqual(27, len(material_items))
        self.assertEqual(set(names), {item.name for item in material_items})
        self.assertEqual(27, len({item.target_id for item in material_items}))
        self.assertEqual(
            "ff-mech-core",
            next(item.target_id for item in material_items
                 if item.name == "FF Mech Core"),
        )
        self.assertEqual(
            ["waveworn-residue-239"],
            [item.target_id for item in catalog.search(
                "waveworn residue 239", kind=TargetKind.MATERIAL)],
        )
        self.assertEqual(
            ["ff-autopuppet-kernel"],
            [item.target_id for item in catalog.search(
                "AUTOPUPPET", kind=TargetKind.MATERIAL)],
        )

        for item in material_items:
            with self.subTest(material=item.name):
                result = catalog.resolve(TargetKind.MATERIAL, item.target_id)
                self.assertEqual((), result.candidate_mob_ids)
                self.assertEqual((), result.qualified_route_ids)
                if item.target_id == "ff-mech-core":
                    self.assertEqual(FarmingReadiness.SOURCE_DOCUMENTED,
                                     result.readiness)
                    self.assertEqual(5, len(result.documented_mob_ids))
                else:
                    self.assertEqual(FarmingReadiness.SOURCE_UNRESOLVED,
                                     result.readiness)
                    self.assertEqual((), result.documented_mob_ids)
                    self.assertEqual((), catalog.documented_sources(item.target_id))

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

    def test_verified_drop_without_route_is_not_ready(self):
        result = self.catalog(drops=(self.drop,)).resolve(
            TargetKind.MATERIAL, "material-1",
            source_is_qualified=lambda _: True,
        )
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)
        self.assertEqual(("mob-1",), result.candidate_mob_ids)

    def test_route_metadata_alone_never_enables_farming(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        result = catalog.resolve(TargetKind.MATERIAL, "material-1",
                                 source_is_qualified=lambda _: True)
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)
        self.assertEqual((), result.qualified_route_ids)

    def test_explicit_failed_verification_still_blocks(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1",
            route_is_qualified=lambda _: False,
            source_is_qualified=lambda _: True,
        )
        self.assertEqual(FarmingReadiness.ROUTE_UNQUALIFIED, result.readiness)

    def test_explicit_current_runtime_verifier_can_release_candidate(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        observed = []
        def qualified(route):
            observed.append(route.route_id)
            return route.route_id == "route-1"
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1", route_is_qualified=qualified,
            source_is_qualified=lambda _: True,
        )
        self.assertEqual(FarmingReadiness.READY, result.readiness)
        self.assertEqual(("route-1",), result.qualified_route_ids)
        self.assertEqual(["route-1"], observed)

    def test_documented_source_never_permits_execution(self):
        documented = DocumentedMobDrop(
            "material-1", "mob-1", "https://example.org/material-drop",
        )
        catalog = self.catalog(documented=(documented,), routes=(self.route,))
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1",
            route_is_qualified=lambda _: True,
            source_is_qualified=lambda _: True,
        )
        self.assertEqual(FarmingReadiness.SOURCE_DOCUMENTED, result.readiness)
        self.assertEqual(("mob-1",), result.documented_mob_ids)
        self.assertEqual((), result.candidate_mob_ids)
        self.assertEqual((), result.qualified_route_ids)
        self.assertEqual(
            (documented,), catalog.documented_sources("material-1"),
        )

    def test_evidence_label_without_source_verifier_is_not_enough(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1",
            route_is_qualified=lambda _: True,
        )
        self.assertEqual(FarmingReadiness.SOURCE_UNRESOLVED, result.readiness)
        self.assertEqual((), result.qualified_route_ids)

    def test_source_failure_blocks_route_even_with_successful_route_verifier(self):
        catalog = self.catalog(drops=(self.drop,), routes=(self.route,))
        result = catalog.resolve(
            TargetKind.MATERIAL, "material-1",
            route_is_qualified=lambda _: True,
            source_is_qualified=lambda _: False,
        )
        self.assertEqual(FarmingReadiness.SOURCE_UNRESOLVED, result.readiness)

    def test_invalid_documented_source_and_unknown_mappings_rejected(self):
        for url in ("http://example.org/a", "https://", "https://u:p@x.example/a",
                    "https://example.org/has space"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                DocumentedMobDrop("material-1", "mob-1", url)
        item = DocumentedMobDrop("material-1", "mob-1", "https://example.org/a")
        with self.assertRaises(ValueError):
            self.catalog(documented=(item, item))
        with self.assertRaises(ValueError):
            self.catalog(documented=(DocumentedMobDrop(
                "missing", "mob-1", "https://example.org/a"),))
        with self.assertRaises(ValueError):
            self.catalog().documented_sources("unknown")

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
