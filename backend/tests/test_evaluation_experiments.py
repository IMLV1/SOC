from uuid import uuid4

from app.evaluation.experiments import compare


def test_ab_runs_pinned_detectors_on_same_dataset_and_c_stays_unavailable():
    instance_id = uuid4()
    event_id = uuid4()
    events = [
        {
            "id": event_id,
            "scenario_instance_id": instance_id,
            "fixture_event_key": "blocked-1",
            "source": "web",
            "username": "synthetic-user",
            "src_ip": "192.0.2.44",
            "asset_id": "web-01",
            "offset_ms": 1,
            "response_json": {"status": 403},
            "log_json": {"event_type": "request_policy_denied"},
        }
    ]
    truth = [
        {
            "scenario_instance_id": instance_id,
            "incident_key": "blocked-request",
            "threat_label": False,
            "expected_evidence_keys": ["blocked-1"],
        }
    ]
    versions = {
        "rule_version": "rules-v2",
        "baseline_version": "baseline-v2",
        "correlation_version": "correlation-v2",
    }

    result = compare(events, truth, versions)

    assert result["A"]["status"] == result["B"]["status"] == "completed"
    assert result["A"]["findings"] and result["B"]["findings"]
    assert result["A"]["metrics"]["fp"] == result["B"]["metrics"]["fp"] == 1
    assert all(
        "ยังไม่มีหลักฐานว่าเข้าถึงระบบสำเร็จ" in item["explanation"]
        for arm in ("A", "B")
        for item in result[arm]["findings"]
    )
    assert result["C"]["status"] == "unavailable"
    assert result["C"]["metrics"] is None
