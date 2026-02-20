"""Kanibako error hierarchy."""


class ClodboxError(Exception):
    """Base exception for all kanibako errors."""


class ConfigError(ClodboxError):
    """Configuration file missing or malformed."""


class ProjectError(ClodboxError):
    """Project path does not exist or cannot be resolved."""


class ContainerError(ClodboxError):
    """Container runtime or image operation failed."""


class ArchiveError(ClodboxError):
    """Archive creation, extraction, or validation failed."""


class GitError(ClodboxError):
    """Git check failed (uncommitted changes, unpushed commits, etc.)."""


class CredentialError(ClodboxError):
    """Credential copy or merge failed."""


class UserCancelled(ClodboxError):
    """User cancelled an interactive prompt."""
