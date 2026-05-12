import unittest

from asimovbm_client.runner import ParticipantCodeError, load_callable


class ParticipantLoadingTests(unittest.TestCase):
    def test_loads_sample_transformer(self):
        transformer = load_callable("examples.policies.sample_policy:SampleTransformer")

        self.assertTrue(callable(transformer))

    def test_missing_module_reports_setup_error(self):
        with self.assertRaisesRegex(ParticipantCodeError, "Could not import"):
            load_callable("missing.module:Policy")

    def test_missing_callable_interface_reports_setup_error(self):
        with self.assertRaisesRegex(ParticipantCodeError, "not callable"):
            load_callable("tests.runner.test_loading:NOT_CALLABLE")


NOT_CALLABLE = object()
