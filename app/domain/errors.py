class ExternalServiceError(RuntimeError):
    """Raised by adapters when a call to Gmail or the LLM provider fails."""
