import urllib.error

from lib.http_client import NonRetryableHTTPError, _error_from_http_error


def test_krx_http_403_is_non_retryable_because_kind_blocks_vercel_egress_by_ip():
    # KIND WAF 403s on Vercel are IP-based and do not recover in seconds;
    # retrying just burns the budget and doubles up Telegram alert traffic.
    error = urllib.error.HTTPError(
        'https://kind.krx.co.kr/investwarn/investattentwarnrisky.do',
        403,
        'Forbidden',
        {},
        None,
    )

    mapped = _error_from_http_error('krx', error)

    assert isinstance(mapped, NonRetryableHTTPError)
    assert mapped.status == 403
