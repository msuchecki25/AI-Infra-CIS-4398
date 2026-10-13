"""Repository-level compatibility package for the RAWBerry API app."""

from pathlib import Path

# The deployable API package owns shared retrieval code. Expose it here too so
# repository-level users can keep importing ``app.retrieval``.
_api_app = Path(__file__).resolve().parent.parent / "rawberry-api" / "app"
if _api_app.is_dir():
    __path__.append(str(_api_app))
