from types import SimpleNamespace
from unittest.mock import MagicMock

from app.config import Settings
from app.services.chat_service import ChatService
from app.services.gemini_service import GeminiChatClient, MockChatClient
from app.store import InMemoryStore


def test_gemini_client_falls_back_to_mock_response_when_disabled():
    settings = Settings(gemini_api_key=None, use_mock_chat=True)
    client = GeminiChatClient(settings)

    assert client.generate_reply("hello") == "You said: hello"


def test_gemini_client_uses_real_client_when_enabled(monkeypatch):
    settings = Settings(gemini_api_key="test-key", use_mock_chat=False)

    fake_client = MagicMock()
    fake_response = MagicMock()
    fake_response.text = "hi from gemini"
    fake_client.models.generate_content.return_value = fake_response

    monkeypatch.setattr(
        "app.services.gemini_service.genai",
        SimpleNamespace(Client=MagicMock(return_value=fake_client)),
    )

    client = GeminiChatClient(settings)
    assert client.generate_reply("hello") == "hi from gemini"


def test_chat_service_uses_mock_client_by_default():
    settings = Settings(gemini_api_key=None, use_mock_chat=True)
    store = InMemoryStore()

    service = ChatService(store, settings=settings)
    response = service.generate_reply_from_message("hello")

    assert response == "You said: hello"
    assert isinstance(service.llm_client, MockChatClient)


def test_chat_service_uses_gemini_when_available():
    store = InMemoryStore()
    fake_llm = MagicMock()
    fake_llm.generate_reply.return_value = "hello from gemini"

    service = ChatService(store, llm_client=fake_llm)
    response = service.generate_reply_from_message("hello")

    assert response == "hello from gemini"
