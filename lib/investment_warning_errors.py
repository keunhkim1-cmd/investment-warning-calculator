"""Shared error type for investment-warning status modules."""
from __future__ import annotations


class InvestmentWarningStatusError(RuntimeError):
    def __init__(self, message: str, code: str = 'PROVIDER_ERROR'):
        super().__init__(message)
        self.code = code
