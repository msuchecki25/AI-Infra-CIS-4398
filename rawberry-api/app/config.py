import os
from dataclasses import dataclass

#this class tells the GeminiChatClient whether to use a real Gemini client or a mock client
#  based on the settings and environment variables.
@dataclass(frozen=True)
class Settings:
    gemini_model: str = "gemini-2.5-flash"
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    use_mock_chat: bool = True

    @classmethod
    # Read application settings from environment variables.
    def from_env(cls) -> "Settings":
        raw_use_mock = os.getenv("USE_MOCK_CHAT", "true").strip().lower()
        use_mock_chat = raw_use_mock not in {"false", "0", "no", "off"}

        project = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or os.getenv("GOOGLE_CLOUD_PROJECT_ID")
        )

        return cls(
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            google_cloud_project=project,
            google_cloud_location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"),
            use_mock_chat=use_mock_chat,
        )


# Return the current application settings.
def get_settings() -> Settings:
    return Settings.from_env()


settings = Settings.from_env()
