"""Exceptions for LeshanClient."""


class LeshanClientError(Exception):
    """Generic LeshanClient exception."""


class LeshanClientEmptyResponseError(Exception):
    """LeshanClient empty API response exception."""


class LeshanClientConnectionError(LeshanClientError):
    """LeshanClient connection exception."""


class LeshanClientConnectionTimeoutError(LeshanClientConnectionError):
    """LeshanClient connection Timeout exception."""

