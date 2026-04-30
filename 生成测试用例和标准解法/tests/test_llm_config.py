from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from llm_config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT_SECONDS,
    DotEnvError,
    LLMConfig,
    load_dotenv_values,
)


class LLMConfigTests(unittest.TestCase):
    def test_load_dotenv_values_supports_comments_empty_lines_and_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                """
# 注释
OPENAI_API_KEY="test-key"
OPENAI_MODEL='test-model'
OPENAI_BASE_URL=https://example.test/v1 # 行尾注释
HASH_VALUE=abc#def
EMPTY_VALUE=
""".lstrip(),
                encoding="utf-8",
            )

            values = load_dotenv_values(env_path)

        self.assertEqual(values["OPENAI_API_KEY"], "test-key")
        self.assertEqual(values["OPENAI_MODEL"], "test-model")
        self.assertEqual(values["OPENAI_BASE_URL"], "https://example.test/v1")
        self.assertEqual(values["HASH_VALUE"], "abc#def")
        self.assertEqual(values["EMPTY_VALUE"], "")

    def test_from_dotenv_uses_defaults_for_optional_numeric_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                """
OPENAI_API_KEY=test-key
OPENAI_MODEL=test-model
""".lstrip(),
                encoding="utf-8",
            )

            config = LLMConfig.from_dotenv(env_path)

        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.model, "test-model")
        self.assertIsNone(config.base_url)
        self.assertEqual(config.temperature, DEFAULT_TEMPERATURE)
        self.assertEqual(config.timeout_seconds, DEFAULT_TIMEOUT_SECONDS)
        self.assertEqual(config.max_retries, DEFAULT_MAX_RETRIES)

    def test_from_dotenv_reads_optional_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                """
OPENAI_API_KEY=test-key
OPENAI_MODEL=test-model
OPENAI_BASE_URL=https://example.test/v1
OPENAI_TEMPERATURE=0.7
OPENAI_TIMEOUT_SECONDS=15
OPENAI_MAX_RETRIES=4
""".lstrip(),
                encoding="utf-8",
            )

            config = LLMConfig.from_dotenv(env_path)

        self.assertEqual(config.base_url, "https://example.test/v1")
        self.assertEqual(config.temperature, 0.7)
        self.assertEqual(config.timeout_seconds, 15.0)
        self.assertEqual(config.max_retries, 4)

    def test_missing_dotenv_file_fails_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            with self.assertRaisesRegex(DotEnvError, "找不到 .env 文件"):
                LLMConfig.from_dotenv(env_path)

    def test_missing_required_values_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("OPENAI_API_KEY=test-key\n", encoding="utf-8")

            with self.assertRaisesRegex(DotEnvError, "OPENAI_MODEL"):
                LLMConfig.from_dotenv(env_path)

    def test_invalid_numeric_values_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                """
OPENAI_API_KEY=test-key
OPENAI_MODEL=test-model
OPENAI_MAX_RETRIES=abc
""".lstrip(),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(DotEnvError, "OPENAI_MAX_RETRIES"):
                LLMConfig.from_dotenv(env_path)


if __name__ == "__main__":
    unittest.main()
