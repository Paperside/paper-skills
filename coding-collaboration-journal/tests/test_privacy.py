from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from common import sanitize, secret_hits  # noqa: E402


class PrivacyTests(unittest.TestCase):
    def test_low_keeps_context_but_removes_secrets(self) -> None:
        payload = {
            "cwd": "/company/payments-service",
            "file_path": "src/callback.ts",
            "api_key": "super-secret",
            "text": "use Bearer abc.def.ghi.jkl and sk-abcdefghijklmnopqrstuvwxyz",
        }
        result = sanitize(payload, "Low")
        self.assertEqual(result["cwd"], payload["cwd"])
        self.assertEqual(result["file_path"], payload["file_path"])
        self.assertEqual(result["api_key"], "[REDACTED_SECRET]")
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", result["text"])
        self.assertNotIn("abc.def.ghi.jkl", result["text"])

    def test_text_assignments_headers_urls_and_jwts_are_redacted(self) -> None:
        samples = [
            '"api_key": "ordinary-looking-secret"',
            "ANTHROPIC_API_KEY=ordinary-looking-secret",
            "Authorization: Basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==",
            "Cookie: sessionid=abc123",
            "eyJabcdefghij.abcdefghij.abcdefghij",
            "https://alice:secret@example.com/repo.git",
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                result = sanitize(sample, "Low")
                self.assertFalse(secret_hits(result), result)
                self.assertNotIn("ordinary-looking-secret", result)
                self.assertNotIn("sessionid=abc123", result)
                self.assertNotIn("alice:secret", result)

    def test_non_secret_metrics_and_policy_names_are_preserved(self) -> None:
        self.assertEqual(sanitize("token_count=123", "Low"), "token_count=123")
        self.assertEqual(sanitize("secret_strategy=rotate", "Low"), "secret_strategy=rotate")
        self.assertEqual(sanitize("not_password_policy=rotate", "Low"), "not_password_policy=rotate")
        self.assertEqual(sanitize("token=opaque-value", "Low"), "token=[REDACTED_SECRET]")


    def test_camel_case_secret_keys_are_redacted(self) -> None:
        result = sanitize(
            {
                "apiKey": "a",
                "accessToken": "b",
                "clientSecret": "c",
                "privateKey": "d",
                "tokenCount": 42,
            },
            "Low",
        )
        self.assertEqual(result["apiKey"], "[REDACTED_SECRET]")
        self.assertEqual(result["accessToken"], "[REDACTED_SECRET]")
        self.assertEqual(result["clientSecret"], "[REDACTED_SECRET]")
        self.assertEqual(result["privateKey"], "[REDACTED_SECRET]")
        self.assertEqual(result["tokenCount"], 42)

    def test_high_abstracts_native_container_payloads(self) -> None:
        result = sanitize(
            {
                "threads": [{"cwd": "/company/repo", "turns": [{"message": "secret design"}]}],
                "sessions": [{"records": [{"text": "implementation"}]}],
                "repositories": [{"root": "/company/repo"}],
                "selected_thread_count": 1,
            },
            "High",
        )
        self.assertTrue(result["threads"]["abstracted"])
        self.assertTrue(result["sessions"]["abstracted"])
        self.assertTrue(result["repositories"]["abstracted"])
        self.assertEqual(result["selected_thread_count"], 1)

    def test_medium_aliases_business_sensitive_keys(self) -> None:
        result = sanitize({"customer_email": "alice@example.com", "decision": "keep retries"}, "Medium")
        self.assertTrue(result["customer_email"]["aliased"])
        self.assertEqual(result["decision"], "keep retries")

    def test_high_abstracts_implementation_fields(self) -> None:
        result = sanitize(
            {
                "cwd": "/secret/repo",
                "content": "source code",
                "repo_name": "payments-service",
                "filename": "src/callback.ts",
                "event_type": "Stop",
            },
            "High",
        )
        self.assertTrue(result["cwd"]["abstracted"])
        self.assertTrue(result["content"]["abstracted"])
        self.assertTrue(result["repo_name"]["abstracted"])
        self.assertTrue(result["filename"]["abstracted"])
        self.assertEqual(result["event_type"], "Stop")


if __name__ == "__main__":
    unittest.main()
