from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from execution_config import (
    DEFAULT_BRUTEFORCE_MEMORY_LIMIT_MB,
    DEFAULT_BRUTEFORCE_TIMEOUT_SECONDS,
    DEFAULT_CHECKER_MEMORY_LIMIT_MB,
    DEFAULT_CHECKER_TIMEOUT_SECONDS,
    DEFAULT_TEST_INPUT_MEMORY_LIMIT_MB,
    DEFAULT_TEST_INPUT_TIMEOUT_SECONDS,
    ExecutionConfig,
)
from llm_config import DotEnvError


class ExecutionConfigTests(unittest.TestCase):
    def test_missing_dotenv_uses_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config = ExecutionConfig.from_dotenv(Path(temp_dir) / ".env")

        self.assertEqual(config.test_input_timeout_seconds, DEFAULT_TEST_INPUT_TIMEOUT_SECONDS)
        self.assertEqual(config.test_input_memory_limit_mb, DEFAULT_TEST_INPUT_MEMORY_LIMIT_MB)
        self.assertEqual(config.bruteforce_timeout_seconds, DEFAULT_BRUTEFORCE_TIMEOUT_SECONDS)
        self.assertEqual(config.bruteforce_memory_limit_mb, DEFAULT_BRUTEFORCE_MEMORY_LIMIT_MB)
        self.assertEqual(config.checker_timeout_seconds, DEFAULT_CHECKER_TIMEOUT_SECONDS)
        self.assertEqual(config.checker_memory_limit_mb, DEFAULT_CHECKER_MEMORY_LIMIT_MB)

    def test_from_dotenv_reads_execution_limits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                """
EXECUTION_TEST_INPUT_TIMEOUT_SECONDS=1.5
EXECUTION_TEST_INPUT_MEMORY_LIMIT_MB=128
EXECUTION_BRUTEFORCE_TIMEOUT_SECONDS=2.5
EXECUTION_BRUTEFORCE_MEMORY_LIMIT_MB=256
EXECUTION_CHECKER_TIMEOUT_SECONDS=3.5
EXECUTION_CHECKER_MEMORY_LIMIT_MB=384
""".lstrip(),
                encoding="utf-8",
            )

            config = ExecutionConfig.from_dotenv(env_path)

        self.assertEqual(config.test_input_timeout_seconds, 1.5)
        self.assertEqual(config.test_input_memory_limit_mb, 128)
        self.assertEqual(config.bruteforce_timeout_seconds, 2.5)
        self.assertEqual(config.bruteforce_memory_limit_mb, 256)
        self.assertEqual(config.checker_timeout_seconds, 3.5)
        self.assertEqual(config.checker_memory_limit_mb, 384)

    def test_invalid_execution_limit_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("EXECUTION_CHECKER_MEMORY_LIMIT_MB=0\n", encoding="utf-8")

            with self.assertRaisesRegex(DotEnvError, "EXECUTION_CHECKER_MEMORY_LIMIT_MB"):
                ExecutionConfig.from_dotenv(env_path)


if __name__ == "__main__":
    unittest.main()
