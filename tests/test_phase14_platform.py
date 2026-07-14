from __future__ import annotations

import unittest

from prepdrill_content.phase14 import ClientCapabilities, ClientEvent, ClientStateReducer, Phase14Evaluator, PlatformRegistry, SubjectPack


class Phase14PlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = PlatformRegistry.open()
        self.pack = SubjectPack("english", "ugc_net", "paper_2_english", 1, "tax.v1", ("single_choice",), ("paragraph",), 2, 1, True)
        self.repo.register_pack(self.pack)

    def test_separate_authorization_and_capabilities(self) -> None:
        capabilities = ClientCapabilities("web", 1, ("single_choice",), ("paragraph",))
        self.assertFalse(self.repo.can_start(pack_id="english", current_corpus_fingerprint="fp", capabilities=capabilities))
        self.repo.authorize(pack_id="english", corpus_fingerprint="fp", gate_passed=True, owner="owner", reason="reviewed")
        self.assertTrue(self.repo.can_start(pack_id="english", current_corpus_fingerprint="fp", capabilities=capabilities))
        self.assertFalse(self.repo.can_start(pack_id="english", current_corpus_fingerprint="other", capabilities=capabilities))

    def test_client_state_parity(self) -> None:
        events = [ClientEvent(1, "answer", 0, "A"), ClientEvent(2, "submit")]
        reducer = ClientStateReducer()
        web = reducer.reduce(pack=self.pack, events=events, answer_key={0: "A"}, question_count=1, initial_seconds=60)
        ios = reducer.reduce(pack=self.pack, events=list(events), answer_key={0: "A"}, question_count=1, initial_seconds=60)
        self.assertTrue(reducer.assert_parity([web, ios]))
        self.assertEqual(web.score, 2)

    def test_evaluator(self) -> None:
        result = Phase14Evaluator().run()
        self.assertTrue(result.passed, result.to_dict())
        self.assertGreaterEqual(len(result.checks), 11)


if __name__ == "__main__":
    unittest.main()
