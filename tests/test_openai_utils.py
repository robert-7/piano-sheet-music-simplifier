import unittest
from unittest import mock

import httpx2
import openai

from src.piano_learning.utils import openai_utils


class AgentClientTests(unittest.TestCase):
    def test_agent_path_registers_async_client(self):
        # The Agents SDK's set_default_openai_client requires an AsyncOpenAI.
        # Before the fix, a synchronous openai.OpenAI was passed instead.
        captured: dict[str, object] = {}

        def fake_set_default(client):
            captured["client"] = client

        fake_result = mock.Mock(final_output="<score/>")

        with mock.patch.object(openai_utils, "set_default_openai_client", fake_set_default), \
                mock.patch.object(openai_utils, "Agent", mock.Mock()), \
                mock.patch.object(openai_utils, "Runner") as runner:
            runner.run_sync.return_value = fake_result
            openai_utils.run_openai_response_with_agent(
                timeout=httpx2.Timeout(60.0),
                model="gpt-5.5",
                instructions="do it",
                input_text="<score/>",
                api_key="test-key",
            )

        self.assertIn("client", captured)
        self.assertIsInstance(captured["client"], openai.AsyncOpenAI)


if __name__ == "__main__":
    unittest.main()
