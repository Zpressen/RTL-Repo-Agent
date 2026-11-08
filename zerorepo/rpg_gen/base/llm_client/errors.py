"""Request failures that must not enter prompt/JSON repair loops."""


class LLMRequestError(RuntimeError):
    """An unsuccessful API request, after any transport retries."""

    def __init__(self, message, **diagnostics):
        super().__init__(message)
        self.diagnostics = diagnostics


class LLMRequestTimeoutError(LLMRequestError):
    """A supervised deadline expired; explicit timeout policies decide retries."""


class IncompleteLLMResponseError(LLMRequestError):
    """The stream ended without a complete response; discard and retry it."""


class LLMResponseTruncatedError(LLMRequestError):
    """The model exhausted the output limit; identical retries cannot fix it."""
