"""Exercise anonymous HTTPS boundaries with synthetic streaming responses only."""

from dataclasses import replace
import hashlib
import json

import httpx
import pytest

from odin_mcp import public_http
from odin_mcp.config import SETTINGS
from odin_mcp.public_http import Budget, PublicDataError


METADATA_URL = "https://odin-smr.org/parquet/archive/index.json"
PARQUET_URL = "https://odin-smr.org/l2/project=synthetic/profile.parquet"


class RecordedStream(httpx.SyncByteStream):
    def __init__(self, chunks, before_chunk=None):
        self.chunks = chunks
        self.before_chunk = before_chunk
        self.yielded = 0
        self.closed = False

    def __iter__(self):
        for chunk in self.chunks:
            if self.before_chunk:
                self.before_chunk()
            self.yielded += 1
            yield chunk

    def close(self):
        self.closed = True


def response(body=b"{}", *, status=200, headers=None, stream=None):
    return httpx.Response(
        status,
        headers=headers or {},
        stream=stream if stream is not None else httpx.ByteStream(body),
    )


@pytest.fixture
def mock_http(monkeypatch):
    """Use the production client configuration, replacing only network transport."""
    original_client = httpx.Client

    def install(handler):
        requests = []

        def record(request):
            requests.append(request)
            return handler(request)

        def make_client(*args, **kwargs):
            return original_client(*args, transport=httpx.MockTransport(record), **kwargs)

        monkeypatch.setattr(public_http.httpx, "Client", make_client)
        return requests

    return install


@pytest.mark.parametrize(
    ("url", "kind"),
    [
        (METADATA_URL, "metadata"),
        ("https://odin-smr.org/parquet/catalog.json", "metadata"),
        ("https://odin-smr.org/parquet/archive/snapshot-20261115/g-synthetic.json", "metadata"),
        (PARQUET_URL, "parquet"),
        ("https://odin-smr.org/parquet/releases/example-v1/profile.parquet", "parquet"),
    ],
)
def test_public_catalog_and_data_paths_are_accepted(url, kind):
    assert public_http.validate_public_url(url, kind=kind) == url


@pytest.mark.parametrize(
    "url",
    [
        "http://odin-smr.org/l2/profile.parquet",
        "https://odin-smr.org.evil.example/l2/profile.parquet",
        "https://www.odin-smr.org/l2/profile.parquet",
        "https://odin-smr.org./l2/profile.parquet",
        "https://127.0.0.1/l2/profile.parquet",
        "https://odin-smr.org:443/l2/profile.parquet",
        "https://reader:synthetic@odin-smr.org/l2/profile.parquet",
        "https://odin-smr.org/l2/profile.parquet?signature=synthetic",
        "https://odin-smr.org/l2/profile.parquet#fragment",
        "https://odin-smr.org/l2/../private/profile.parquet",
        "https://odin-smr.org/l2/./profile.parquet",
        "https://odin-smr.org/l2/%2e%2e/private/profile.parquet",
        "https://odin-smr.org/l2/%252e%252e/private/profile.parquet",
        "https://odin-smr.org/l2/part%2Fprofile.parquet",
        "https://odin-smr.org/l2/part%252fprofile.parquet",
        "https://odin-smr.org/l2/part%5cprofile.parquet",
        "https://odin-smr.org/l2/part\\profile.parquet",
        "https://odin-smr.org/l2//profile.parquet",
        "https://odin-smr.org/l2/%00profile.parquet",
        "https://odin-smr.org/l2/%0aprofile.parquet",
        "https://odin-smr.org/l2/%GGprofile.parquet",
        "https://odin-smr.org/l2/profile .parquet",
        "https://odin-smr.org/private/profile.parquet",
        "https://odin-smr.org/l2/profile.json",
        "s3://synthetic/profile.parquet",
        None,
        3,
    ],
)
def test_unsafe_urls_are_rejected_before_any_request(mock_http, url):
    requests = mock_http(lambda request: response())
    budget = Budget()
    with pytest.raises(PublicDataError):
        public_http.fetch_bytes(url, budget, purpose="download")
    assert requests == []
    assert budget.requests == 0


@pytest.mark.parametrize("encoded", ["\x7f", "%7f", "%257F"])
def test_delete_control_character_is_not_a_public_url(mock_http, encoded):
    requests = mock_http(lambda request: response())
    with pytest.raises(PublicDataError):
        public_http.fetch_bytes(
            f"https://odin-smr.org/l2/{encoded}profile.parquet", Budget(), purpose="download"
        )
    assert requests == []


@pytest.mark.parametrize(
    "url",
    [
        PARQUET_URL,
        "https://odin-smr.org/api/products",
        "https://odin-smr.org/parquet/archive/arbitrary.json",
        "https://odin-smr.org/parquet/archive/snapshot/not-a-group.json",
        "https://odin-smr.org/parquet/archive/%2e%2e/g-synthetic.json",
    ],
)
def test_metadata_requests_are_limited_to_known_catalog_paths(mock_http, url):
    requests = mock_http(lambda request: response())
    with pytest.raises(PublicDataError):
        public_http.fetch_json(url, Budget())
    assert requests == []


def test_metadata_path_resolution_does_not_accept_another_origin():
    assert public_http.absolute_metadata_url("/parquet/catalog.json") == "https://odin-smr.org/parquet/catalog.json"
    assert public_http.absolute_metadata_url(METADATA_URL) == METADATA_URL
    with pytest.raises(PublicDataError):
        public_http.absolute_metadata_url("//foreign.example/parquet/catalog.json")


def test_requests_ignore_environment_authentication_proxies_and_response_cookies(mock_http, monkeypatch, tmp_path):
    netrc = tmp_path / "synthetic.netrc"
    netrc.write_text("machine odin-smr.org login synthetic password unused\n", encoding="utf-8")
    monkeypatch.setenv("NETRC", str(netrc))
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setenv("ALL_PROXY", "http://proxy.invalid:9999")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setenv("SSL_CERT_FILE", str(tmp_path / "missing-ca.pem"))
    requests = mock_http(lambda request: response(
        b'{"schema_version":1}', headers={"Set-Cookie": "session=synthetic; Path=/; Secure"}
    ))
    budget = Budget()
    public_http.fetch_json(METADATA_URL, budget)
    public_http.fetch_json(METADATA_URL, budget)
    assert len(requests) == 2
    for request in requests:
        assert request.method == "GET"
        assert "authorization" not in request.headers
        assert "proxy-authorization" not in request.headers
        assert "cookie" not in request.headers
        assert request.headers["accept-encoding"] == "identity"
        assert request.extensions["timeout"]["connect"] == 5.0
        assert request.extensions["timeout"]["read"] == 15.0


@pytest.mark.parametrize("status", [301, 302, 307, 308, 401, 403, 404, 412, 429, 500])
def test_error_status_and_redirects_do_not_follow_or_read_response_body(mock_http, status):
    stream = RecordedStream([b"synthetic private response detail"])
    requests = mock_http(lambda request: response(
        status=status, headers={"Location": "https://foreign.example/"}, stream=stream
    ))
    with pytest.raises(PublicDataError, match=f"HTTP {status}") as error:
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download")
    assert len(requests) == 1
    assert stream.yielded == 0
    assert stream.closed
    assert "private response detail" not in str(error.value)


@pytest.mark.parametrize("error_type", [httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout])
def test_timeout_returns_actionable_error_without_retry(mock_http, error_type):
    def timeout(request):
        raise error_type("synthetic internal timeout detail", request=request)

    requests = mock_http(timeout)
    with pytest.raises(PublicDataError, match="timed out") as error:
        public_http.fetch_json(METADATA_URL, Budget())
    assert len(requests) == 1
    assert "internal timeout detail" not in str(error.value)


def test_transport_failure_does_not_return_partial_bytes(mock_http):
    def failure(request):
        raise httpx.RemoteProtocolError("synthetic transport detail", request=request)

    mock_http(failure)
    with pytest.raises(PublicDataError, match="no complete result") as error:
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download")
    assert "synthetic transport detail" not in str(error.value)


@pytest.mark.parametrize("encoding", ["gzip", "br", "deflate"])
def test_encoded_responses_are_rejected_before_decompression(mock_http, encoding):
    stream = RecordedStream([b"not decoded"])
    mock_http(lambda request: response(headers={"Content-Encoding": encoding}, stream=stream))
    with pytest.raises(PublicDataError, match="Encoded HTTP responses"):
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download")
    assert stream.yielded == 0
    assert stream.closed


@pytest.mark.parametrize("purpose", ["metadata", "download"])
def test_declared_oversized_response_is_rejected_without_reading_body(mock_http, purpose):
    stream = RecordedStream([b"123456789"])
    mock_http(lambda request: response(headers={"Content-Length": "9"}, stream=stream))
    budget = Budget(settings=replace(SETTINGS, max_file_bytes=8, max_metadata_response_bytes=8))
    url = METADATA_URL if purpose == "metadata" else PARQUET_URL
    with pytest.raises(PublicDataError, match="byte budget"):
        public_http.fetch_bytes(url, budget, purpose=purpose)
    assert stream.yielded == 0
    assert stream.closed
    assert budget.metadata_bytes == budget.download_bytes == 0


@pytest.mark.parametrize("length", ["-1", "+3", "three", "3.0", "3, 3"])
def test_invalid_content_length_is_rejected_before_body_read(mock_http, length):
    stream = RecordedStream([b"123"])
    mock_http(lambda request: response(headers={"Content-Length": length}, stream=stream))
    with pytest.raises(PublicDataError, match="Content-Length"):
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download")
    assert stream.yielded == 0


@pytest.mark.parametrize("purpose", ["metadata", "download"])
def test_streamed_response_cap_stops_a_chunked_body_early(mock_http, purpose):
    chunk = b"x" * 65536
    stream = RecordedStream([chunk, chunk, chunk])
    mock_http(lambda request: response(stream=stream))
    budget = Budget(settings=replace(SETTINGS, max_file_bytes=len(chunk), max_metadata_response_bytes=len(chunk)))
    with pytest.raises(PublicDataError, match="byte budget"):
        public_http.fetch_bytes(METADATA_URL if purpose == "metadata" else PARQUET_URL, budget, purpose=purpose)
    assert stream.yielded == 2
    assert stream.closed


@pytest.mark.parametrize("purpose", ["metadata", "download"])
def test_total_budget_applies_across_multiple_successful_files(mock_http, purpose):
    requests = mock_http(lambda request: response(b"12345", headers={"Content-Length": "5"}))
    budget = Budget(settings=replace(SETTINGS, max_download_bytes=9, max_metadata_bytes=9))
    url = METADATA_URL if purpose == "metadata" else PARQUET_URL
    assert public_http.fetch_bytes(url, budget, purpose=purpose)[0] == b"12345"
    with pytest.raises(PublicDataError, match="byte budget"):
        public_http.fetch_bytes(url, budget, purpose=purpose)
    assert len(requests) == 2
    assert getattr(budget, "metadata_bytes" if purpose == "metadata" else "download_bytes") == 5


@pytest.mark.parametrize("purpose", ["metadata", "download"])
def test_total_streamed_budget_is_enforced_without_content_length(mock_http, purpose):
    streams = [RecordedStream([b"123456"]), RecordedStream([b"7890", b"unread"])]
    selected = iter(streams)
    mock_http(lambda request: response(stream=next(selected)))
    budget = Budget(settings=replace(SETTINGS, max_download_bytes=9, max_metadata_bytes=9))
    url = METADATA_URL if purpose == "metadata" else PARQUET_URL
    assert public_http.fetch_bytes(url, budget, purpose=purpose)[0] == b"123456"
    with pytest.raises(PublicDataError, match="byte budget"):
        public_http.fetch_bytes(url, budget, purpose=purpose)
    assert streams[1].yielded == 1, "A cumulative limit must stop before the next transport chunk"
    assert streams[1].closed


def test_expected_size_can_reject_a_file_without_making_a_request(mock_http):
    requests = mock_http(lambda request: response())
    budget = Budget(settings=replace(SETTINGS, max_file_bytes=8, max_download_bytes=10), download_bytes=4)
    with pytest.raises(PublicDataError, match="download budget"):
        public_http.fetch_bytes(PARQUET_URL, budget, purpose="download", expected_size=7)
    assert requests == []
    assert budget.requests == 0


@pytest.mark.parametrize("headers", [{"Content-Length": "5"}, {}])
def test_downloaded_size_must_match_catalog_with_or_without_length_header(mock_http, headers):
    mock_http(lambda request: response(b"12345", headers=headers))
    with pytest.raises(PublicDataError, match="size differs"):
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download", expected_size=4)


@pytest.mark.parametrize("body", [b"123", b"12345"])
def test_content_length_mismatch_cannot_be_returned_as_success(mock_http, body):
    mock_http(lambda request: response(body, headers={"Content-Length": "4"}))
    with pytest.raises(PublicDataError, match="Incomplete HTTP response"):
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download")


@pytest.mark.parametrize("etag", [None, '"changed"', 'W/"synthetic-etag"'])
def test_catalog_etag_requires_matching_strong_response_validator(mock_http, etag):
    stream = RecordedStream([b"1234"])
    headers = {"ETag": etag} if etag is not None else {}
    requests = mock_http(lambda request: response(headers=headers, stream=stream))
    with pytest.raises(PublicDataError, match="ETag differs"):
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download", expected_etag="synthetic-etag")
    assert requests[0].headers["if-match"] == '"synthetic-etag"'
    assert stream.yielded == 0


def test_invalid_catalog_etag_never_reaches_a_request_header(mock_http):
    requests = mock_http(lambda request: response())
    with pytest.raises(PublicDataError, match="Invalid catalog ETag"):
        public_http.fetch_bytes(PARQUET_URL, Budget(), purpose="download", expected_etag="synthetic\r\nInjected: value")
    assert requests == []


def test_success_receipt_preserves_source_validator_and_computed_digest(mock_http):
    data = b"PAR1syntheticPAR1"
    headers = {"Content-Length": str(len(data)), "ETag": '"synthetic-etag"', "Last-Modified": "Sun, 15 Nov 2026 00:00:00 GMT"}
    mock_http(lambda request: response(data, headers=headers))
    budget = Budget(settings=replace(SETTINGS, max_file_bytes=len(data), max_download_bytes=len(data)))
    body, receipt = public_http.fetch_bytes(
        PARQUET_URL, budget, purpose="download", expected_size=len(data), expected_etag="synthetic-etag"
    )
    assert body == data
    assert receipt == {
        "url": PARQUET_URL,
        "size_bytes": len(data),
        "etag": headers["ETag"],
        "last_modified": headers["Last-Modified"],
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    assert budget.download_bytes == len(data)
    assert budget.requests == 1


@pytest.mark.parametrize(
    "body",
    [
        b"not JSON",
        b"\xff",
        b'{"schema_version":1,"value":NaN}',
        b'{"schema_version":1,"value":Infinity}',
        b'{"schema_version":1,"value":-Infinity}',
        b'{"schema_version":1,"nested":{"values":[1e9999]}}',
        b'{"schema_version":1,"value":-1e9999}',
    ],
)
def test_metadata_requires_valid_finite_json(mock_http, body):
    mock_http(lambda request: response(body))
    with pytest.raises(PublicDataError, match="valid finite JSON"):
        public_http.fetch_json(METADATA_URL, Budget())


@pytest.mark.parametrize("document", [[], None, 1, {}, {"schema_version": 2}, {"schema_version": True}, {"schema_version": 1.0}])
def test_metadata_requires_object_with_integer_schema_version_one(mock_http, document):
    mock_http(lambda request: response(json.dumps(document).encode()))
    with pytest.raises(PublicDataError, match="catalog schema"):
        public_http.fetch_json(METADATA_URL, Budget())


def test_request_cap_prevents_an_additional_http_operation(mock_http):
    requests = mock_http(lambda request: response(b'{"schema_version":1}'))
    budget = Budget(settings=replace(SETTINGS, max_http_requests=2))
    public_http.fetch_json(METADATA_URL, budget)
    public_http.fetch_json(METADATA_URL, budget)
    with pytest.raises(PublicDataError, match="request budget"):
        public_http.fetch_json(METADATA_URL, budget)
    assert len(requests) == budget.requests == 2


def test_expired_operation_does_not_start_http(mock_http, monkeypatch):
    requests = mock_http(lambda request: response())
    monkeypatch.setattr(public_http.time, "monotonic", lambda: 61.0)
    budget = Budget(settings=replace(SETTINGS, operation_timeout_seconds=60), started=0.0)
    with pytest.raises(PublicDataError, match="deadline exceeded"):
        public_http.fetch_json(METADATA_URL, budget)
    assert requests == []
    assert budget.requests == 0


def test_deadline_is_checked_between_streamed_chunks(mock_http, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(public_http.time, "monotonic", lambda: now[0])

    def advance():
        now[0] += 31.0

    stream = RecordedStream([b"x" * 65536] * 3, before_chunk=advance)
    mock_http(lambda request: response(stream=stream))
    budget = Budget(settings=replace(SETTINGS, operation_timeout_seconds=60), started=0.0)
    with pytest.raises(PublicDataError, match="deadline exceeded"):
        public_http.fetch_bytes(PARQUET_URL, budget, purpose="download")
    assert stream.yielded == 2
    assert stream.closed


def test_small_slow_chunks_do_not_hide_the_operation_deadline(mock_http, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(public_http.time, "monotonic", lambda: now[0])

    def advance():
        now[0] += 31.0

    stream = RecordedStream([b"a", b"b", b"c"], before_chunk=advance)
    mock_http(lambda request: response(stream=stream))
    budget = Budget(settings=replace(SETTINGS, operation_timeout_seconds=60), started=0.0)
    with pytest.raises(PublicDataError, match="deadline exceeded"):
        public_http.fetch_bytes(PARQUET_URL, budget, purpose="download")
    assert stream.yielded == 2, "The expired second transport chunk must stop the read before the third chunk"
    assert stream.closed


def test_empty_response_still_checks_deadline_before_success(mock_http, monkeypatch):
    now = [0.0]
    monkeypatch.setattr(public_http.time, "monotonic", lambda: now[0])

    def delayed_empty_response(request):
        now[0] = 61.0
        return response(b"")

    mock_http(delayed_empty_response)
    budget = Budget(settings=replace(SETTINGS, operation_timeout_seconds=60), started=0.0)
    with pytest.raises(PublicDataError, match="deadline exceeded"):
        public_http.fetch_bytes(PARQUET_URL, budget, purpose="download")
