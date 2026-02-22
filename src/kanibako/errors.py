"""Kanibako error hierarchy."""


class KanibakoError(Exception):
    """Base exception for all kanibako errors."""


class ConfigError(KanibakoError):
    """Configuration file missing or malformed."""


class ProjectError(KanibakoError):
    """Project path does not exist or cannot be resolved."""


class ContainerError(KanibakoError):
    """Container runtime or image operation failed."""


class ArchiveError(KanibakoError):
    """Archive creation, extraction, or validation failed."""


class GitError(KanibakoError):
    """Git check failed (uncommitted changes, unpushed commits, etc.)."""


class WorksetError(KanibakoError):
    """Workset creation, loading, or manipulation failed."""


class UserCancelled(KanibakoError):
    """User cancelled an interactive prompt."""
