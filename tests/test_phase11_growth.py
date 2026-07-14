from __future__ import annotations

import unittest

from prepdrill_content.phase11 import GrowthRepository, Phase11Evaluator, PublicContent, PublicPageGate


class Phase11GrowthTests(unittest.TestCase):
    def test_public_page_gate(self) -> None:
        gate = PublicPageGate()
        eligible = PublicContent("1", "slug", "Title", "published", "clear", "licensed", True, True, "official_previous_year", "hash")
        blocked = PublicContent("2", "blocked", "Blocked", "published", "clear", "unknown", True, True, "official_previous_year", "hash2")
        self.assertTrue(gate.eligible(eligible))
        self.assertFalse(gate.eligible(blocked))
        self.assertEqual(gate.sitemap([blocked, eligible], base_url="https://example.com"), ["https://example.com/questions/slug"])

    def test_attribution_merge_and_conversion_dedup(self) -> None:
        repo = GrowthRepository.open()
        repo.touch(subject_type="guest", subject_id="g", campaign="telegram", epoch=1)
        repo.touch(subject_type="guest", subject_id="g", campaign="youtube", epoch=2)
        merged = repo.merge_guest(guest_id="g", account_id="u")
        self.assertEqual((merged["first_campaign"], merged["last_campaign"]), ("telegram", "youtube"))
        self.assertEqual(repo.record_conversion(account_id="u", conversion_type="activation", epoch=3), repo.record_conversion(account_id="u", conversion_type="activation", epoch=4))

    def test_evaluator(self) -> None:
        result = Phase11Evaluator().run()
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(len(result.checks), 12)


if __name__ == "__main__":
    unittest.main()
