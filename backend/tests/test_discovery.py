import unittest

from pydantic import ValidationError

from app.routers.discovery import DiscoverRequest


class DiscoveryEndpointTests(unittest.TestCase):
    def test_discovery_rejects_result_budget_above_phase_cap(self):
        with self.assertRaises(ValidationError):
            DiscoverRequest(
                question="efficient transformer inference",
                max_results=21,
            )


if __name__ == "__main__":
    unittest.main()
