import os

from app.config import Settings, get_settings

try:
    from google import genai
except ModuleNotFoundError:  # pragma: no cover
    genai = None


class MockChatClient:
    def generate_reply(self, message: str) -> str:
        return f"You said: {message}"


class GeminiChatClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def should_use_real_client(self) -> bool:
        if self.settings.use_mock_chat:
            return False

        if self.settings.gemini_api_key:
            return True

        project = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        )
        return bool(project)

    def generate_reply(self, message: str) -> str:
        if not self.should_use_real_client():
            return MockChatClient().generate_reply(message)

        if genai is None:
            raise RuntimeError("google-genai is not installed. Install it from requirements.txt.")

        try:
            if self.settings.gemini_api_key:
                client = genai.Client(api_key=self.settings.gemini_api_key)
            else:
                project = (
                    os.getenv("GOOGLE_CLOUD_PROJECT")
                    or os.getenv("GCLOUD_PROJECT")
                    or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
                )
                if not project:
                    raise RuntimeError(
                        "Vertex AI project is not configured. Set GOOGLE_CLOUD_PROJECT or use GEMINI_API_KEY."
                    )

                location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
                client = genai.Client(
                    vertexai=True,
                    project=project,
                    location=location,
                )

            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=message,
            )
            text = getattr(response, "text", None)
            if text:
                return text.strip() or MockChatClient().generate_reply(message)
            return str(response).strip() or MockChatClient().generate_reply(message)
        except Exception:
            if self.settings.use_mock_chat:
                return MockChatClient().generate_reply(message)
            raise
