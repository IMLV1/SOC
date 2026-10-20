"""Pinned, explainable detectors over released events only."""

import re
from collections import defaultdict
from typing import Any

from app.detection.policy_v1 import Finding
from app.detection.policy_v1 import evaluate as evaluate_v1

RULE_VERSION = "rules-v2"
BASELINE_VERSION = "baseline-v2"
CORRELATION_VERSION = "correlation-v2"
LOGIN_THRESHOLD = 10
WINDOW_MS = 300_000
SCAN_THRESHOLD = 4
ANOMALY_WINDOW_MS = 60_000
MIN_READ_EVENTS = 3
RECORDS_PER_BASELINE_READ = 100
ANOMALY_RATIO = 8
CONFIG = {
    "login_threshold": LOGIN_THRESHOLD,
    "window_ms": WINDOW_MS,
    "scan_threshold": SCAN_THRESHOLD,
    "scan_window_ms": WINDOW_MS,
    "anomaly_window_ms": ANOMALY_WINDOW_MS,
    "min_read_events": MIN_READ_EVENTS,
    "records_per_baseline_read": RECORDS_PER_BASELINE_READ,
    "anomaly_ratio": ANOMALY_RATIO,
    "correlation_fields": ["scenario_instance", "account", "session", "asset", "time"],
}


def _ordered(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda row: (row["offset_ms"], str(row["id"])))


def _context(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["scenario_instance_id"]),
        row["username"],
        str(row["src_ip"]),
        row["asset_id"],
    )


def _rules(events: list[dict[str, Any]]) -> list[Finding]:
    # Detection intentionally groups evidence by a stable scenario/account/IP/asset
    # tuple. A matching event elsewhere in the run cannot complete this chain.
    findings: list[Finding] = []
    auth: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    scans: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    ordered = _ordered(events)

    for row in ordered:
        context = _context(row)
        kind = row["log_json"].get("event_type")
        if row["source"] == "authentication":
            auth[context].append(row)
        if kind == "scanner_request":
            scans[context].append(row)
        if kind == "request_policy_denied" or row["response_json"].get("status") == 403:
            findings.append(
                Finding(
                    "rule",
                    RULE_VERSION,
                    f"blocked:{context}:{row['id']}",
                    "Blocked web request",
                    "low",
                    "Request ถูกปฏิเสธโดย policy; ยังไม่มีหลักฐานว่าเข้าถึงระบบสำเร็จ",
                    (row["id"],),
                )
            )

    for context, group in auth.items():
        failed = [row for row in group if row["log_json"].get("event_type") == "login_failed"]
        window = next(
            (
                failed[end - LOGIN_THRESHOLD + 1 : end + 1]
                for end in range(LOGIN_THRESHOLD - 1, len(failed))
                if failed[end]["offset_ms"] - failed[end - LOGIN_THRESHOLD + 1]["offset_ms"]
                <= WINDOW_MS
            ),
            None,
        )
        if not window:
            continue
        start, last = window[0]["offset_ms"], window[-1]["offset_ms"]
        successes = [
            row
            for row in group
            if row["log_json"].get("event_type") == "session_created"
            and row["log_json"].get("session_id")
            and last <= row["offset_ms"] <= start + WINDOW_MS
        ]
        # A successful login alone is not evidence of impact; require reads tied
        # to that exact session and the same account, source address, and scenario.
        impacts: dict[tuple[str, str, str, str], tuple[dict[str, Any], list[dict[str, Any]]]] = {}
        for success in successes:
            session_id = success["log_json"]["session_id"]
            for row in ordered:
                if (
                    row["log_json"].get("event_type") == "records_read"
                    and _context(row)[0] == context[0]
                    and row["username"] == success["username"]
                    and str(row["src_ip"]) == str(success["src_ip"])
                    and row["log_json"].get("session_id") == session_id
                    and success["offset_ms"] <= row["offset_ms"] <= start + WINDOW_MS
                ):
                    key = (session_id, row["asset_id"], row["username"], str(row["src_ip"]))
                    if key not in impacts:
                        impacts[key] = (success, [])
                    impacts[key][1].append(row)
        if not impacts:
            findings.append(
                Finding(
                    "rule",
                    RULE_VERSION,
                    f"auth:{context}:{start}",
                    "Repeated login failures",
                    "medium",
                    "พบ login ล้มเหลวอย่างน้อย 10 ครั้งใน 5 นาที; ยังไม่ยืนยันผลกระทบ",
                    tuple(row["id"] for row in window),
                )
            )
        for (session_id, asset_id, username, ip), (success, reads) in impacts.items():
            findings.append(
                Finding(
                    "rule",
                    RULE_VERSION,
                    f"auth:{context[0]}:{username}:{session_id}:{asset_id}:{ip}:{start}",
                    "Login attempts followed by data access",
                    "high",
                    "พบ session, asset และการอ่านข้อมูลที่สัมพันธ์กันในช่วงเวลา; ยังต้องยืนยันเจ้าของกิจกรรม",
                    tuple(row["id"] for row in window + [success] + reads),
                )
            )

    for context, group in scans.items():
        window = next(
            (
                group[index : index + SCAN_THRESHOLD]
                for index in range(len(group) - SCAN_THRESHOLD + 1)
                if group[index + SCAN_THRESHOLD - 1]["offset_ms"] - group[index]["offset_ms"]
                <= WINDOW_MS
            ),
            None,
        )
        if not window:
            continue
        change_ref = window[0]["log_json"].get("change_ref")
        approved: list[dict[str, Any]] = []
        # Approval lowers the finding severity only when the whole scan window
        # fits the approved asset and time range; a shared change ID is insufficient.
        if change_ref and all(row["log_json"].get("change_ref") == change_ref for row in window):
            for change in ordered:
                log = change["log_json"]
                match = re.fullmatch(
                    r"([^;]+); offsets ([0-9]+)-([0-9]+)ms", log.get("scope") or ""
                )
                if (
                    log.get("event_type") == "approved_scan_window"
                    and log.get("change_ref") == change_ref
                    and _context(change) == context
                    and match
                    and match[1] == context[3]
                    and all(
                        change["offset_ms"] <= row["offset_ms"]
                        and int(match[2]) <= row["offset_ms"] <= int(match[3])
                        for row in window
                    )
                ):
                    approved.append(change)
        findings.append(
            Finding(
                "rule",
                RULE_VERSION,
                f"scan:{context}:{window[0]['offset_ms']}",
                "Security scan activity",
                "low" if approved else "medium",
                "พบการสแกนตรงกับบัญชี/IP/asset/เวลาและ change record อนุมัติ"
                if approved
                else "พบการสแกนที่ยังยืนยัน scope/time ของการอนุมัติไม่ได้",
                tuple(row["id"] for row in approved + window),
            )
        )
    return findings


def _anomalies(events: list[dict[str, Any]]) -> list[Finding]:
    ordered = _ordered(events)
    baselines: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    reads: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in ordered:
        kind = row["log_json"].get("event_type")
        key = (str(row["scenario_instance_id"]), row["username"], row["asset_id"])
        if kind == "historical_read_rate":
            baselines[key].append(row)
        elif kind == "records_read" and row["log_json"].get("session_id"):
            reads[key].append(row)

    findings: list[Finding] = []
    for key, baseline_rows in baselines.items():
        for baseline in baseline_rows:
            rate = baseline["log_json"].get("baseline_reads_per_minute")
            if not isinstance(rate, int) or rate <= 0:
                continue
            candidates = [
                row
                for row in reads.get(key, [])
                if row["log_json"].get("session_id")
                and baseline["offset_ms"]
                <= row["offset_ms"]
                <= baseline["offset_ms"] + ANOMALY_WINDOW_MS
            ]
            by_session: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in candidates:
                by_session[row["log_json"]["session_id"]].append(row)
            for session_id, group in by_session.items():
                if len(group) < MIN_READ_EVENTS:
                    continue
                # Compare the observed volume against the run's own historical
                # rate, and require several events to avoid a one-record spike.
                volume = sum(int(row["log_json"].get("records_read") or 0) for row in group)
                expected = rate * RECORDS_PER_BASELINE_READ
                if volume < expected * ANOMALY_RATIO:
                    continue
                context = (*key, session_id, str(baseline["src_ip"]))
                findings.append(
                    Finding(
                        "anomaly",
                        BASELINE_VERSION,
                        f"read-volume:{context}:{baseline['offset_ms']}",
                        "Unusual data-read volume",
                        "high",
                        f"อ่าน {volume} records ใน 60 วินาที เทียบ baseline {rate} reads/min; "
                        "ต้องตรวจบริบทก่อนสรุปสาเหตุ",
                        tuple([baseline["id"], *(row["id"] for row in group)]),
                    )
                )
    return findings


def evaluate(events: list[dict[str, Any]]) -> list[Finding]:
    """Evaluate only supplied events; callers pass released rows from one run."""
    return _rules(events) + _anomalies(events)


def evaluate_pinned(
    events: list[dict[str, Any]], rule: str, baseline: str, correlation: str
) -> list[Finding]:
    # Runs retain their detector versions so a later deployment cannot silently
    # reinterpret findings that were produced under an older policy.
    if (rule, baseline, correlation) == ("rules-v1", "baseline-v1", "correlation-v1"):
        return evaluate_v1(events)
    if (rule, baseline, correlation) != (
        RULE_VERSION,
        BASELINE_VERSION,
        CORRELATION_VERSION,
    ):
        raise ValueError("Unsupported pinned detector policy")
    return evaluate(events)
