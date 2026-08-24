import unittest

from app.llm.structured import (
    StructuredOutputError,
    StructuredValidationError,
    generate_structured_payload,
    parse_json_object,
    validate_json_object,
)


TEST_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "value": {"type": "string"},
    },
    "required": ["value"],
}


class StructuredOutputTests(unittest.TestCase):
    def test_generate_structured_payload_validates_native_result(self):
        payload = generate_structured_payload(
            messages=[{"role": "user", "content": "Return value"}],
            schema_name="test_schema",
            schema=TEST_SCHEMA,
            native_generate=lambda *_: {"value": "ok"},
            text_generate=lambda *_: self.fail("text fallback should not run"),
        )

        self.assertEqual(payload, {"value": "ok"})

    def test_native_tier_receives_a_schema_with_a_title(self):
        """langchain-openai refuses a dict schema without a top-level title.

        When the native tier fails, every structured call silently pays for
        the slower JSON-text fallback - the post-upgrade slowdown.
        """
        seen = {}

        def native(messages, model, temperature, schema):
            seen["schema"] = schema
            return {"value": "ok"}

        generate_structured_payload(
            messages=[{"role": "user", "content": "Return value"}],
            schema_name="test_schema",
            schema=TEST_SCHEMA,
            native_generate=native,
            text_generate=lambda *_: self.fail("text fallback should not run"),
        )

        self.assertEqual(seen["schema"]["title"], "test_schema")
        # The original schema object must not be mutated.
        self.assertNotIn("title", TEST_SCHEMA)

    def test_an_existing_schema_title_is_preserved(self):
        seen = {}

        def native(messages, model, temperature, schema):
            seen["schema"] = schema
            return {"value": "ok"}

        generate_structured_payload(
            messages=[{"role": "user", "content": "Return value"}],
            schema_name="test_schema",
            schema={"title": "custom_name", **TEST_SCHEMA},
            native_generate=native,
            text_generate=lambda *_: self.fail("text fallback should not run"),
        )

        self.assertEqual(seen["schema"]["title"], "custom_name")

    def test_parse_json_object_strips_code_fences(self):
        payload = parse_json_object('```json\n{"value": "ok"}\n```')
        self.assertEqual(payload, {"value": "ok"})

    def test_validate_json_object_raises_for_schema_mismatch(self):
        with self.assertRaises(StructuredValidationError):
            validate_json_object({"wrong": "shape"}, TEST_SCHEMA)

    def test_generate_structured_payload_repairs_invalid_fallback_once(self):
        calls = []

        def text_generate(messages, model, temperature):
            calls.append((messages, model, temperature))
            if len(calls) == 1:
                return '{"wrong": "shape"}'
            return '{"value": "repaired"}'

        payload = generate_structured_payload(
            messages=[{"role": "user", "content": "Return value"}],
            schema_name="test_schema",
            schema=TEST_SCHEMA,
            native_generate=lambda *_: (_ for _ in ()).throw(RuntimeError("native failed")),
            text_generate=text_generate,
        )

        self.assertEqual(payload, {"value": "repaired"})
        self.assertEqual(len(calls), 2)

    def test_generate_structured_payload_stops_after_single_repair_retry(self):
        calls = []

        def text_generate(messages, model, temperature):
            calls.append((messages, model, temperature))
            return '{"wrong": "shape"}'

        with self.assertRaises(StructuredOutputError):
            generate_structured_payload(
                messages=[{"role": "user", "content": "Return value"}],
                schema_name="test_schema",
                schema=TEST_SCHEMA,
                native_generate=lambda *_: (_ for _ in ()).throw(RuntimeError("native failed")),
                text_generate=text_generate,
            )

        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
