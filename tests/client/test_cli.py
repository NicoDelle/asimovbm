import unittest

from asimovbm_client.cli import main


class CliTests(unittest.TestCase):
    def test_help_exits_successfully(self):
        with self.assertRaises(SystemExit) as context:
            main(["--help"])

        self.assertEqual(context.exception.code, 0)

    def test_missing_required_arguments_exits_with_setup_error(self):
        with self.assertRaises(SystemExit) as context:
            main([])

        self.assertEqual(context.exception.code, 2)

    def test_runs_sample_policy_against_fake_backend(self):
        code = main(
            [
                "--server",
                "fake://local",
                "--run-token",
                "run-1",
                "--robot-package",
                "examples/robot_packages/minimal",
                "--transformer",
                "examples.policies.sample_policy:SampleTransformer",
                "--policy",
                "examples.policies.sample_policy:SamplePolicy",
            ]
        )

        self.assertEqual(code, 0)

    def test_real_server_requires_run_or_bootstrap_token(self):
        code = main(
            [
                "--server",
                "http://127.0.0.1:8000",
                "--robot-package",
                "examples/robot_packages/minimal",
                "--transformer",
                "examples.policies.sample_policy:SampleTransformer",
                "--policy",
                "examples.policies.sample_policy:SamplePolicy",
            ]
        )

        self.assertEqual(code, 2)
