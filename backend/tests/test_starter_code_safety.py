import unittest

from app.services.paper_implementation import (
    _review_starter_code_deterministically,
    _unsafe_starter_code_reasons,
)


class UnsafeStarterCodeFalsePositiveTests(unittest.TestCase):
    """Ordinary starter code and prose must survive the safety review.

    Every case here was rejected by the original substring scan.
    """

    def assertAllowed(self, content: str, path: str):
        self.assertEqual(
            _unsafe_starter_code_reasons(content, path=path),
            [],
            f"{path} should not be flagged: {content!r}",
        )

    def test_model_eval_is_not_dynamic_execution(self):
        """model.eval() appears in nearly every PyTorch evaluation path."""
        self.assertAllowed("model.eval()\nwith torch.no_grad():\n    pass", "train.py")

    def test_attribute_spawn_is_not_process_execution(self):
        self.assertAllowed("# use mp.spawn( for multi-gpu\n", "train.py")

    def test_readme_may_document_download_commands(self):
        self.assertAllowed("## Setup\n\ncurl -O https://example.org/d.zip", "README.md")
        self.assertAllowed("Download with wget https://example.org/d.tar", "README.md")

    def test_readme_may_name_model_providers(self):
        self.assertAllowed("Compared against OpenAI GPT-4 baselines.", "README.md")
        self.assertAllowed("Baselines include Gemini and Claude.", "docs/notes.md")

    def test_readme_may_mention_api_keys_in_prose(self):
        self.assertAllowed("Set your api_key if using a hosted model.", "README.md")

    def test_commented_out_calls_are_ignored(self):
        self.assertAllowed("# TODO: load_dataset(name) once known", "data.py")
        self.assertAllowed("# no socket.io needed here", "net.py")
        self.assertAllowed("# the anthropic principle is unrelated", "model.py")

    def test_download_keyword_argument_is_allowed(self):
        self.assertAllowed('ds = MNIST(root="./d", download=True)', "data.py")

    def test_identifiers_containing_pattern_words(self):
        self.assertAllowed("evaluation_steps = 100", "train.py")
        self.assertAllowed("request_dim = 512", "model.py")


class UnsafeStarterCodeDetectionTests(unittest.TestCase):
    """Genuinely unsafe code must still be rejected."""

    def assertFlagged(self, content: str, path: str, label: str):
        self.assertIn(
            label,
            _unsafe_starter_code_reasons(content, path=path),
            f"{path} should be flagged: {content!r}",
        )

    def test_network_calls(self):
        self.assertFlagged(
            "import requests\nr = requests.get(url)", "data.py", "network calls"
        )
        self.assertFlagged("urlretrieve(url, path)", "data.py", "network calls")

    def test_shell_execution(self):
        self.assertFlagged(
            'import subprocess\nsubprocess.run(["sh"])',
            "run.py",
            "shell or process execution",
        )
        self.assertFlagged('os.system("rm -rf /")', "run.py", "shell or process execution")

    def test_bare_dynamic_execution(self):
        self.assertFlagged("eval(user_input)", "x.py", "dynamic code execution")
        self.assertFlagged("exec(code)", "x.py", "dynamic code execution")

    def test_dataset_downloads_in_code(self):
        self.assertFlagged('ds = load_dataset("wmt14")', "d.py", "dataset downloads")
        self.assertFlagged("dataset.download()", "d.py", "dataset downloads")

    def test_provider_sdk_usage(self):
        self.assertFlagged("import openai", "llm.py", "API key or provider usage")
        self.assertFlagged("client = openai.OpenAI()", "llm.py", "API key or provider usage")
        self.assertFlagged('api_key = "sk-abc"', "c.py", "API key or provider usage")

    def test_documentation_is_still_scanned_for_executable_risk(self):
        """Exempting prose groups must not turn .md into a blind spot."""
        self.assertFlagged(
            "import requests; requests.get(u)", "README.md", "network calls"
        )
        self.assertFlagged("eval(payload)", "README.md", "dynamic code execution")


class ReviewIntegrationTests(unittest.TestCase):
    def test_readme_with_setup_commands_survives_review(self):
        files = [
            {"path": "README.md", "content": "## Setup\n\ncurl -O https://x.org/d.zip"},
            {"path": "train.py", "content": "model.eval()"},
        ]
        reviewed, warnings = _review_starter_code_deterministically(files, [])

        self.assertEqual(warnings, [])
        self.assertEqual(
            [f["content"] for f in reviewed], [f["content"] for f in files]
        )

    def test_unsafe_file_is_still_replaced(self):
        files = [{"path": "data.py", "content": "import requests\nrequests.get(u)"}]
        reviewed, warnings = _review_starter_code_deterministically(files, [])

        self.assertTrue(warnings)
        self.assertNotEqual(reviewed[0]["content"], files[0]["content"])


if __name__ == "__main__":
    unittest.main()
