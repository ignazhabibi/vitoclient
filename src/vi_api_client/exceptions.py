"""Exceptions for Viessmann API Client."""

class ViError(Exception):
    """Base exception for Viessmann API."""
    pass

class ViAuthError(ViError):
    """Authentication failed."""
    pass

class ViConnectionError(ViError):
    """Connection issue with the API."""
    pass
