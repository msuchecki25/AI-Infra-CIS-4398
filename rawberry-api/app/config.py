import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com"
    use_mock_chat: bool = True

    @classmethod
    def from_env(cls) -> "Settings":
        raw_use_mock = os.getenv("USE_MOCK_CHAT", "true").strip().lower()
        use_mock_chat = raw_use_mock not in {"false", "0", "no", "off"}

        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            gemini_api_base_url=os.getenv(
                "GEMINI_API_BASE_URL",
                "https://generativelanguage.googleapis.com",
            ),
            use_mock_chat=use_mock_chat,
        )


def get_settings() -> Settings:
    return Settings.from_env()


settings = Settings.from_env()
