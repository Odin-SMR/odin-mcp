from odin_mcp.s3_browser import (
    PartitionFilters,
    _build_prefix,
    _parse_partition_value,
    list_parquet_files,
)


class _FakeClient:
    def __init__(self):
        self.called_with = None

    def list_objects_v2(self, **kwargs):
        self.called_with = kwargs
        return {
            "Contents": [
                {"Key": "project=ALL-Strat-v3.0.0/month=01/a.parquet"},
                {"Key": "project=ALL-Strat-v3.0.0/month=01/b.parquet"},
                {"Key": "project=ALL-Strat-v3.0.0/month=01/notes.txt"},
            ],
            "NextContinuationToken": "token-2",
        }


def test_build_prefix_stops_on_missing_value():
    filters = PartitionFilters(project="ALL-Strat-v3.0.0", inv_mode="stnd")
    assert _build_prefix(filters) == "project=ALL-Strat-v3.0.0/"


def test_parse_partition_value():
    assert _parse_partition_value("project=meso21/", "project") == "meso21"
    assert _parse_partition_value("month=01/", "project") is None


def test_list_parquet_files_filters_and_limits(monkeypatch):
    import odin_mcp.s3_browser as mod

    fake = _FakeClient()

    class _Settings:
        bucket = "odin-level2"
        max_list_results = 1000

    monkeypatch.setattr(mod, "SETTINGS", _Settings())
    monkeypatch.setattr(mod, "_client", lambda: fake)

    res = list_parquet_files(
        filters=PartitionFilters(project="ALL-Strat-v3.0.0"),
        limit=1,
        continuation_token="token-1",
    )

    assert res["s3_uris"] == [
        "s3://odin-level2/project=ALL-Strat-v3.0.0/month=01/a.parquet"
    ]
    assert res["next_token"] == "token-2"
    assert fake.called_with["ContinuationToken"] == "token-1"
