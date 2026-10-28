import json

import pytest

from app.analysis.investigation_config import current_release, release_snapshot, transport_config
from app.analysis.provider_config import load_config


def test_config_pins_release_without_paths_or_credentials(investigation_release):
    values, _, _ = investigation_release
    snapshot = load_config(values).investigation_snapshot
    assert current_release(snapshot)
    serialized = json.dumps(snapshot)
    assert "synthetic-investigation-key" not in serialized
    assert values["DIFY_ANALYSIS_APP_KEY_FILE"] not in serialized


@pytest.mark.parametrize(
    "change",
    [
        {"status": "draft"},
        {"cost_bound_verified": False},
        {"call_bound_usd": "0"},
        {"max_output_tokens": 4096},
        {"contract_version": "other"},
        {"unapproved": "extra"},
        {"base_url": "http://untrusted.invalid/v1"},
    ],
)
def test_unapproved_release_fails_closed(investigation_release, change):
    values, review, path = investigation_release
    path.write_text(json.dumps(review | change), encoding="utf8")
    with pytest.raises(ValueError, match="RELEASE_UNAVAILABLE"):
        load_config(values)


def test_changed_or_deleted_release_revokes_snapshot(investigation_release):
    values, review, path = investigation_release
    snapshot = release_snapshot(values)
    path.write_text(json.dumps(review | {"model_id": "different-model"}), encoding="utf8")
    assert not current_release(snapshot)
    with pytest.raises(ValueError, match="WITHDRAWN"):
        transport_config(snapshot)
    path.unlink()
    assert not current_release(snapshot)


def test_tutor_key_cannot_be_reused(investigation_release, monkeypatch):
    values, _, _ = investigation_release
    monkeypatch.setenv("DIFY_APP_KEY_FILE", values["DIFY_ANALYSIS_APP_KEY_FILE"])
    with pytest.raises(ValueError, match="SEPARATE_APP_KEY"):
        transport_config(release_snapshot(values))
