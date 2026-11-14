"""Real HTTP contract tests for the standalone read-only Farming Assistant.

These use an ephemeral loopback port and the actual FarmingAssistantView.
No OK Script executor, game process, browser automation, or inputs are involved.
"""
import http.client
import json
import threading
import unittest
from urllib.parse import urlencode

from src.automation.farming_web_server import FarmingWebServer


class TestFarmingStandaloneWeb(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = FarmingWebServer()
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, *, host=None, headers=(), body=None):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.server.server_port, timeout=5
        )
        try:
            connection.putrequest(method, path, skip_host=True)
            if host is None:
                connection.putheader(
                    "Host", f"127.0.0.1:{self.server.server_port}"
                )
            else:
                connection.putheader("Host", host)
            for name, value in headers:
                connection.putheader(name, value)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def read_json(self, path):
        status, headers, body = self.request("GET", path)
        self.assertEqual(200, status, body)
        self.assertIn("application/json", headers["Content-Type"])
        return json.loads(body)

    def test_server_is_bound_to_ipv4_loopback_only(self):
        self.assertEqual("127.0.0.1", self.server.server_address[0])
        self.assertIn(
            f"127.0.0.1:{self.server.server_port}", self.server.base_url
        )
        with self.assertRaises(ValueError):
            FarmingWebServer(port=-1)

    def test_material_discovery_uses_actual_existing_view_contract(self):
        data = self.read_json("/api/targets?" + urlencode({
            "kind": "material", "query": "MECH",
        }))
        self.assertEqual(["ff-mech-core"], [entry["id"] for entry in data])

    def test_all_27_materials_visible_over_read_only_http(self):
        items = self.read_json("/api/targets?kind=material")
        self.assertEqual(27, len(items))
        self.assertEqual("ff-mech-core", items[0]["id"])
        self.assertEqual(27, len({item["id"] for item in items}))
        self.assertIn("premium-sealed-tube", {item["id"] for item in items})
        self.assertIn("ff-carved-crystal", {item["id"] for item in items})

        detail = self.read_json("/api/preview?" + urlencode({
            "kind": "material",
            "target_id": "ff-autopuppet-kernel",
            "desired_total": "12",
        }))
        self.assertEqual("FF Autopuppet Kernel", detail["target"]["name"])
        self.assertEqual("SOURCE_UNRESOLVED", detail["readiness"])
        self.assertEqual([], detail["source_candidates"])
        self.assertEqual("INVENTORY_TOTAL", detail["stop_criterion"]["mode"])
        self.assertEqual(12, detail["stop_criterion"]["requested"])
        self.assertFalse(detail["can_start"])
        self.assertFalse(detail["can_pause"])
        self.assertFalse(detail["can_stop"])

    def test_acquisition_methods_are_cited_but_not_authorized(self):
        for slug, kind in (
            ("premium-sealed-tube", "TACET_FIELD"),
            ("ff-howler-core", "MOB_DROP"),
            ("melodic-string", "FORGERY_CHALLENGE"),
            ("mysterious-code", "EXPLORATION_OR_QUEST"),
        ):
            with self.subTest(material=slug):
                data = self.read_json("/api/preview?" + urlencode({
                    "kind": "material", "target_id": slug,
                }))
                acquisition = data["acquisition_reference"]
                self.assertEqual("REFERENCE_ONLY", acquisition["status"])
                self.assertIn(kind, [m["kind"] for m in acquisition["methods"]])
                self.assertTrue(all(
                    m["reference_url"].startswith("https://")
                    for m in acquisition["methods"]
                ))
                self.assertFalse(acquisition["can_start"])
                self.assertFalse(data["can_start"])
                self.assertEqual([], data["qualified_route_ids"])

    def test_source_strategy_cannot_dispatch_over_http(self):
        for slug, kind in (
            ("presto-helix", "FORGERY_CHALLENGE"),
            ("ff-mech-core", "MOB_DROP"),
            ("mysterious-code", "EXPLORATION_OR_QUEST"),
        ):
            with self.subTest(material=slug):
                preview = self.read_json("/api/preview?" + urlencode({
                    "kind": "material", "target_id": slug,
                }))
                plan = preview["acquisition_plan"]
                self.assertIn(kind, [x["method"] for x in plan["possible_methods"]])
                self.assertFalse(plan["can_dispatch"])
                self.assertIsNone(plan["selected_provider"])
                self.assertEqual([], plan["qualified_provider_ids"])
                self.assertTrue(all(not x["can_execute"]
                                    for x in plan["possible_methods"]))
                self.assertFalse(preview["can_start"])
    def test_source_discovery_is_documented_not_executable(self):
        data = self.read_json("/api/preview?" + urlencode({
            "kind": "material", "target_id": "ff-mech-core",
            "desired_total": 5,
        }))
        self.assertEqual(5, data["stop_criterion"]["requested"])
        self.assertEqual("INVENTORY_TOTAL", data["stop_criterion"]["mode"])
        self.assertEqual("SOURCE_DOCUMENTED", data["readiness"])
        self.assertEqual(5, len(data["source_candidates"]))
        self.assertFalse(data["can_start"])
        self.assertFalse(data["can_pause"])
        self.assertFalse(data["can_stop"])
        self.assertEqual("PREVIEW_ONLY", data["run_state"])
        self.assertIsNone(data["owned_quantity"])
        self.assertEqual([], data["qualified_route_ids"])
        self.assertNotIn("profile_path", json.dumps(data))
        self.assertNotIn("Route Manifest", json.dumps(data))

    def test_mob_stop_criterion_is_encounter_limit(self):
        data = self.read_json("/api/preview?" + urlencode({
            "kind": "mob", "target_id": "geospider-s4",
            "desired_total": "2",
        }))
        self.assertEqual("ENCOUNTER_LIMIT", data["stop_criterion"]["mode"])
        self.assertEqual(2, data["stop_criterion"]["requested"])
        self.assertFalse(data["stop_criterion"]["enforced"])

    def test_static_assets_are_explicitly_allowlisted(self):
        for path, expected in (
            ("/", "text/html"),
            ("/assets/standalone.css", "text/css"),
            ("/assets/standalone.js", "text/javascript"),
            ("/assets/index.js", "text/javascript"),
        ):
            with self.subTest(path=path):
                status, headers, body = self.request("GET", path)
                self.assertEqual(200, status)
                self.assertIn(expected, headers["Content-Type"])
                self.assertTrue(body)

    def test_security_headers_and_no_cors(self):
        _, headers, _ = self.request("GET", "/")
        self.assertEqual("nosniff", headers["X-Content-Type-Options"])
        self.assertEqual("DENY", headers["X-Frame-Options"])
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn("frame-ancestors 'none'",
                      headers["Content-Security-Policy"])
        self.assertNotIn("Access-Control-Allow-Origin", headers)

    def test_wrong_host_header_is_rejected(self):
        for host in (
            "malicious.example", "localhost",
            f"127.0.0.1:{self.server.server_port + 1}",
            "127.0.0.1",
        ):
            with self.subTest(host=host):
                status, _, _ = self.request("GET", "/", host=host)
                self.assertEqual(403, status)

    def test_duplicate_host_header_is_rejected(self):
        status, _, _ = self.request(
            "GET", "/",
            headers=(("Host", f"127.0.0.1:{self.server.server_port}"),),
        )
        self.assertEqual(403, status)

    def test_cross_origin_and_cross_site_requests_rejected(self):
        origin = f"http://127.0.0.1:{self.server.server_port}"
        for headers in (
            (("Origin", "https://attacker.example"),),
            (("Sec-Fetch-Site", "cross-site"),),
            (("Origin", origin), ("Origin", "https://attacker.example")),
        ):
            with self.subTest(headers=headers):
                status, _, _ = self.request("GET", "/api/targets", headers=headers)
                self.assertEqual(403, status)
        status, _, _ = self.request("GET", "/", headers=(("Origin", origin),))
        self.assertEqual(200, status)

    def test_only_get_is_supported(self):
        for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                status, headers, _ = self.request(method, "/api/preview")
                self.assertEqual(405, status)
                self.assertEqual("GET", headers["Allow"])

    def test_no_control_or_private_artifact_endpoints(self):
        for path in (
            "/api/start", "/api/pause", "/api/stop", "/api/execute",
            "/configs/secret.json", "/logs/ok-ww.log",
            "/assets/../../config.py", "/favicon.ico",
            "/api/targets?kind=material&x=1",
        ):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertIn(status, (400, 404))

    def test_rejects_duplicate_unknown_and_malformed_parameters(self):
        for path in (
            "/api/targets?kind=mob&kind=material",
            "/api/targets?unknown=1",
            "/api/preview?kind=material&target_id=ff-mech-core&extra=1",
            "/api/targets?query",
            "/api/targets?query=%00",
        ):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertEqual(400, status)

    def test_invalid_stop_criterion_rejected(self):
        status, _, _ = self.request(
            "GET", "/api/preview?kind=material&target_id=ff-mech-core&desired_total=0"
        )
        self.assertEqual(400, status)

    def test_get_rejects_body_and_transfer_encoding(self):
        status, _, _ = self.request(
            "GET", "/", headers=(("Content-Length", "1"),),
        )
        self.assertEqual(400, status)
        status, _, _ = self.request(
            "GET", "/", headers=(("Transfer-Encoding", "chunked"),),
        )
        self.assertEqual(400, status)

    def test_unknown_path_never_returns_project_file(self):
        for path in ("/.git/config", "/AGENTS.md", "/src/automation/farming_view.py"):
            with self.subTest(path=path):
                status, _, body = self.request("GET", path)
                self.assertEqual(404, status)
                self.assertNotIn(b"FarmingAssistantView", body)


if __name__ == "__main__":
    unittest.main()
