"""Versioned, explainable detectors. No scenario labels or ground truth are inputs."""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

RULE_VERSION = "rules-v1"
BASELINE_VERSION = "baseline-v1"
CORRELATION_VERSION = "correlation-v1"


@dataclass(frozen=True)
class Finding:
    detector_type: str
    detector_version: str
    correlation_key: str
    title: str
    severity: str
    explanation: str
    evidence_ids: tuple[UUID, ...]


def evaluate(events: list[dict[str, Any]]) -> list[Finding]:
    findings: list[Finding] = []
    auth: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    scans: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    baselines: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        kind = event["log_json"].get("event_type")
        if event["source"] == "authentication":
            auth[(event["username"], str(event["src_ip"]))].append(event)
        if kind == "scanner_request":
            scans[event["username"]].append(event)
        if kind == "records_read":
            reads[event["username"]].append(event)
        if kind == "historical_read_rate":
            baselines[event["username"]].append(event)
        if kind == "request_policy_denied" or event["response_json"].get("status") == 403:
            findings.append(
                Finding(
                    "rule",
                    RULE_VERSION,
                    f"web:blocked:{event['src_ip']}",
                    "Blocked web request",
                    "low",
                    "Request ถูกปฏิเสธโดย policy; ยังไม่มีหลักฐานว่าเข้าถึงระบบสำเร็จ",
                    (event["id"],),
                )
            )
    for (username, ip), group in auth.items():
        failed = [row for row in group if row["log_json"].get("event_type") == "login_failed"]
        if len(failed) < 5:
            continue
        success = [row for row in group if row["log_json"].get("event_type") == "session_created"]
        related_reads = [row for row in reads.get(username, []) if str(row["src_ip"]) == ip]
        evidence = tuple(row["id"] for row in (failed + success + related_reads))
        impact = bool(success and related_reads)
        findings.append(
            Finding(
                "rule",
                RULE_VERSION,
                f"auth:{username}:{ip}",
                "Login attempts followed by data access" if impact else "Repeated login failures",
                "high" if impact else "medium",
                (
                    "พบ session สำเร็จและการอ่านข้อมูลหลังความพยายามเข้าสู่ระบบหลายครั้ง "
                    "ต้องตรวจว่าเจ้าของบัญชีเป็นผู้ทำหรือไม่"
                )
                if impact
                else "พบการเข้าสู่ระบบล้มเหลวหลายครั้ง ยังไม่พบหลักฐานว่าเข้าสู่ระบบสำเร็จ",
                evidence,
            )
        )
    for username, group in scans.items():
        if len(group) < 4:
            continue
        change_refs = {row["log_json"].get("change_ref") for row in group}
        approved = [
            row
            for row in events
            if row["log_json"].get("event_type") == "approved_scan_window"
            and row["log_json"].get("change_ref") in change_refs
        ]
        findings.append(
            Finding(
                "rule",
                RULE_VERSION,
                f"web:scan:{username}",
                "Security scan activity",
                "low" if approved else "medium",
                "พบการสแกนที่มี change record อนุมัติ" if approved else "พบการสแกนที่ยังไม่พบการอนุมัติ",
                tuple(row["id"] for row in approved + group),
            )
        )
    for username, group in reads.items():
        baseline = baselines.get(username, [])
        if not baseline or len(group) < 3:
            continue
        rate = baseline[-1]["log_json"].get("baseline_reads_per_minute")
        if not isinstance(rate, int) or rate <= 0:
            continue
        volume = sum(row["log_json"].get("records_read", 0) or 0 for row in group)
        if volume < rate * 100:
            continue
        findings.append(
            Finding(
                "anomaly",
                BASELINE_VERSION,
                f"file:volume:{username}",
                "Unusual data-read volume",
                "high",
                f"อ่าน {volume} records เทียบ baseline {rate} reads/min; ต้องตรวจบริบทก่อนสรุปสาเหตุ",
                tuple(row["id"] for row in baseline + group),
            )
        )
    return findings
