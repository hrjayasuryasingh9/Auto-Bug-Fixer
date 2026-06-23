"""Server-side credential access.

Credentials now live in the environment (.env) instead of being collected and
stored per-user. Callers no longer pass GitHub/Anthropic creds in request bodies.
"""
import os


def github_token() -> str:
    return os.environ.get("GITHUB_TOKEN", "")


def github_owner() -> str:
    return os.environ.get("GITHUB_OWNER", "")


def github_repo() -> str:
    return os.environ.get("GITHUB_REPO", "")


def anthropic_key() -> str:
    return os.environ.get("ANTHROPIC_API_KEY", "")


def openai_key() -> str:
    return os.environ.get("OPENAI_API_KEY", "")
