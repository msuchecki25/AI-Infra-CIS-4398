import os

from app.config import Settings, get_settings

try:
    from google import genai
except ModuleNotFoundError:  # pragma: no cover
    genai = None


class MockChatClient:
    def generate_reply(self, message: str) -> str:
        # Return an echo response without calling Gemini.
        return f"You said: {message}"


class GeminiChatClient:
    def __init__(self, settings: Settings | None = None) -> None:
        # Store the settings used by the Gemini client.
        self.settings = settings or get_settings()

    def _get_project_id(self) -> str | None:
        # Find the Google Cloud project ID in settings or environment variables.
        return (
            self.settings.google_cloud_project
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        )

    def should_use_real_client(self) -> bool:
        # Check whether real Gemini calls are enabled and configured.
        if self.settings.use_mock_chat:
            return False
        return bool(self._get_project_id())

    def generate_reply(self, message: str) -> str:
        # Generate a Gemini response or use the configured mock fallback.
        if not self.should_use_real_client():
            return MockChatClient().generate_reply(message)

        if genai is None:
            raise RuntimeError("google-genai is not installed. Install it from requirements.txt.")

        project = self._get_project_id()
        if not project:
            raise RuntimeError(
                "Vertex AI project is not configured. Set GOOGLE_CLOUD_PROJECT before enabling real Gemini calls."
            )

        location = (
            self.settings.google_cloud_location
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or "global"
        )

        try:
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
