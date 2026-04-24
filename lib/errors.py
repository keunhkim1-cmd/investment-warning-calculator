"""Application and provider error types."""
from lib.retry import RetryableError


class AppError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int = 500,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


class ProviderError(AppError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        provider: str,
        provider_status: str | int | None = None,
        http_status: int = 502,
        details: dict | None = None,
    ):
        merged_details = dict(details or {})
        if provider_status is not None:
            merged_details.setdefault('providerStatus', provider_status)
        super().__init__(
            code,
            message,
            http_status=http_status,
            details=merged_details,
        )
        self.provider = provider
        self.provider_status = provider_status


class RetryableProviderError(ProviderError, RetryableError):
    def __init__(self, *args, retry_after: float | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class DartError(ProviderError):
    pass


class RetryableDartError(DartError, RetryableError):
    def __init__(self, *args, retry_after: float | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.retry_after = retry_after


class NaverError(ProviderError):
    pass


class KrxError(ProviderError):
    pass


class GeminiError(ProviderError):
    pass
