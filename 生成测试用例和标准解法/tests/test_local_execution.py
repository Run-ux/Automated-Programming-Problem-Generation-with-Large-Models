from __future__ import annotations

import unittest

from local_execution import (
    EXECUTION_ERROR,
    EXECUTION_MEMORY_LIMIT,
    EXECUTION_OK,
    EXECUTION_TIMEOUT,
    run_python_function,
)


class LocalExecutionTests(unittest.TestCase):
    def test_run_python_function_returns_value(self) -> None:
        result = run_python_function(
            "def solve(input_str):\n    return input_str.strip() + '!'",
            "solve",
            ["ok"],
            timeout_seconds=2,
            memory_limit_mb=512,
        )

        self.assertEqual(result.status, EXECUTION_OK)
        self.assertEqual(result.return_value, "ok!")

    def test_run_python_function_captures_runtime_error(self) -> None:
        result = run_python_function(
            "def solve(input_str):\n    raise ValueError('bad input')",
            "solve",
            ["x"],
            timeout_seconds=2,
            memory_limit_mb=512,
        )

        self.assertEqual(result.status, EXECUTION_ERROR)
        self.assertEqual(result.phase, "runtime")
        self.assertEqual(result.error_type, "ValueError")
        self.assertIn("bad input", result.error_message)

    def test_run_python_function_captures_timeout(self) -> None:
        result = run_python_function(
            "import time\n\ndef solve(input_str):\n    time.sleep(2)\n    return 'x'",
            "solve",
            [""],
            timeout_seconds=0.2,
            memory_limit_mb=512,
        )

        self.assertEqual(result.status, EXECUTION_TIMEOUT)
        self.assertEqual(result.error_type, "TimeoutExpired")

    def test_run_python_function_captures_memory_limit(self) -> None:
        result = run_python_function(
            "import time\n\ndef solve(input_str):\n    time.sleep(2)\n    return 'x'",
            "solve",
            [""],
            timeout_seconds=5,
            memory_limit_mb=1,
        )

        self.assertEqual(result.status, EXECUTION_MEMORY_LIMIT)
        self.assertEqual(result.error_type, "MemoryLimitExceeded")


if __name__ == "__main__":
    unittest.main()
