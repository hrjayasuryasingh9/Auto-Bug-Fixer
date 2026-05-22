from pydantic import BaseModel
from typing import Optional


class ErrorReport(BaseModel):
    message: str
    repo_url: str
    repo_name: str
    target_file: str
    github_token: str
    github_owner: str
    github_repo: str
    anthropic_api_key: str
    stack: Optional[str] = None
    line_number: Optional[int] = None
    column_number: Optional[int] = None
    url: Optional[str] = None
    userAgent: Optional[str] = None
    timestamp: Optional[int] = None
    componentStack: Optional[str] = None
    sessionId: Optional[str] = None


class FixResponse(BaseModel):
    success: bool
    pr_url: Optional[str] = None
    branch_name: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
