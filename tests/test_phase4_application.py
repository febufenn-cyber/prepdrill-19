from __future__ import annotations

import unittest

from prepdrill_content.phase4 import ApplicationService, IdentitySyncRepository, Phase4Evaluator, StructuredRenderer


class Phase4ApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = IdentitySyncRepository.open()

    def question(self):
        return {
            "published_question_id": "pub:1",
            "question_id": "q:1",
            "question_type": "single_choice",
            "plain_text": "Choose the correct option.",
            "stem_blocks": [{"type": "paragraph", "text": "Choose the correct option."}],
            "options": [{"option_id": "A", "plain_text": "A", "blocks": [{"type": "paragraph", "text": "A"}]}, {"option_id": "B", "plain_text": "B", "blocks": [{"type": "paragraph", "text": "B"}]}],
            "correct_option_id": "A",
            "reviewed_explanation": "hidden",
            "active": True,
        }

    def test_guest_merge_uses_authenticated_account(self) -> None:
        guest = self.repo.create_guest(device_id="d1", onboarding_name="Different Name")
        self.repo.add_progress(owner_type="guest", owner_id=guest["guest_id"], reference_type="attempt", reference_id="a1")
        self.repo.create_or_load_account(auth_user_id="u1", display_name="Account Name")
        self.repo.merge_guest(guest_id=guest["guest_id"], auth_user_id="u1", idempotency_key="m1")
        state = self.repo.load_account_state("u1")
        self.assertEqual(state["account"]["display_name"], "Account Name")
        self.assertEqual(len(state["progress"]), 1)

    def test_service_is_locked_without_activation(self) -> None:
        with self.assertRaises(PermissionError):
            ApplicationService(self.repo, activation_authorized=False).create_flow(owner_id="u", mode="quick", seed="s", idempotency_key="i", questions=[self.question()])

    def test_answers_are_redacted_and_score_is_server_owned(self) -> None:
        service = ApplicationService(self.repo, activation_authorized=True)
        flow = service.create_flow(owner_id="u", mode="quick", seed="s", idempotency_key="i", questions=[self.question()])
        self.assertNotIn("correct_option_id", flow["questions"][0])
        submission = service.submit(flow_id=flow["flow_id"], published_question=self.question(), selected_option_id="B", idempotency_key="submit", client_fields={"correct": True, "score": 10})
        self.assertEqual(submission["correct"], 0)

    def test_renderer_requires_image_alt_text(self) -> None:
        question = self.question()
        question["stem_blocks"] = [{"type": "image"}]
        with self.assertRaises(ValueError):
            StructuredRenderer().render(question)

    def test_evaluator(self) -> None:
        report = Phase4Evaluator().run()
        self.assertTrue(report.passed, report.to_dict())
        self.assertGreaterEqual(len(report.checks), 12)


if __name__ == "__main__":
    unittest.main()
