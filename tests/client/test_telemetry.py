import unittest

from asimovbm_client.protocol import FailureCategory, FailureMessage
from asimovbm_client.telemetry import redact_text, summarize_failures


class TelemetryTests(unittest.TestCase):
    def test_redacts_secret_like_values_and_absolute_paths(self):
        text = redact_text(
            'failed at /home/nico/private/model.py with token=abc123 '
            'Authorization: Bearer xyz "api_key": "secret" password: hunter2'
        )

        self.assertIn("<path>", text)
        self.assertIn("token=<redacted>", text)
        self.assertIn("Authorization: Bearer <redacted>", text)
        self.assertIn('"api_key": "<redacted>"', text)
        self.assertIn("password: <redacted>", text)

    def test_summarizes_failure_categories(self):
        summary = summarize_failures([FailureMessage(FailureCategory.DISCONNECT, "socket closed")])

        self.assertEqual(summary, ["disconnect: socket closed"])
