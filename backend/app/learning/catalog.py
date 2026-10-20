"""A single published, training-only starter lesson. No exam fixtures live here."""

from typing import TypedDict
from uuid import UUID


class LessonStep(TypedDict):
    id: str
    title: str
    target: str
    explanation: str
    limitation: str


class LessonContent(TypedDict):
    id: str
    level_id: str
    version: int
    title: str
    steps: list[LessonStep]


class LessonSummaryData(TypedDict):
    id: str
    version: int
    title: str


class LevelData(TypedDict):
    id: str
    ordinal: int
    title: str
    lessons: list[LessonSummaryData]


LEVEL_ID = UUID("15000000-0000-4000-8000-000000000001")
LESSON_ID = UUID("15000000-0000-4000-8000-000000000101")
LESSON_VERSION = 1
LESSON: LessonContent = {
    "id": str(LESSON_ID),
    "level_id": str(LEVEL_ID),
    "version": LESSON_VERSION,
    "title": "อ่าน HTTP request และผลตอบกลับ",
    "steps": [
        {
            "id": "method_path",
            "title": "Method และ Path",
            "target": "GET /api/profile",
            "explanation": "GET ขออ่าน resource ที่ระบุด้วย path; path บอกว่าระบบถูกขอให้อ่านอะไร",
            "limitation": "คำขอหนึ่งรายการยังไม่บอกว่าใครเป็นผู้ใช้หรือมีข้อมูลใดถูกส่งกลับ",
        },
        {
            "id": "response",
            "title": "Response status",
            "target": "200 OK",
            "explanation": "200 หมายถึงคำขอนี้สำเร็จตาม response ของ endpoint",
            "limitation": "200 ไม่ได้แปลว่ากิจกรรมเป็นภัยหรือผู้ใช้ได้รับข้อมูลเกินสิทธิ์ ต้องตรวจเนื้อหาและบริบท",
        },
        {
            "id": "account_ip",
            "title": "บัญชีและ Source IP",
            "target": "analyst@example.test · 192.0.2.10",
            "explanation": "บัญชีและ IP ช่วยเชื่อมเหตุการณ์ที่อาจมาจากผู้ใช้หรือแหล่งเดียวกัน",
            "limitation": "IP อาจเป็น NAT, VPN หรือ proxy และชื่อบัญชีเพียงอย่างเดียวไม่ยืนยันตัวบุคคล",
        },
        {
            "id": "timeline",
            "title": "Timeline และบริบท",
            "target": "10:02:11Z → 10:02:15Z",
            "explanation": "เรียงเหตุการณ์ตามเวลาเพื่อดูสิ่งที่เกิดก่อนและหลัง request",
            "limitation": "ลำดับเวลาอย่างเดียวไม่พิสูจน์เหตุและผล; ตรวจ clock และ event ที่เกี่ยวข้องด้วย",
        },
        {
            "id": "evidence_limits",
            "title": "สรุปสิ่งที่รู้และยังไม่รู้",
            "target": "request + response + related events",
            "explanation": "ข้อสรุปที่ดีแยกหลักฐานที่เห็นออกจากข้ออนุมาน และบอกข้อมูลที่ยังขาด",
            "limitation": "บทเรียนนี้เป็นตัวอย่างฝึก ไม่ใช่ข้อสอบหรือผลประเมิน",
        },
    ],
}

LEVELS: list[LevelData] = [
    {
        "id": str(LEVEL_ID),
        "ordinal": 1,
        "title": "เริ่มต้น",
        "lessons": [{"id": str(LESSON_ID), "version": LESSON_VERSION, "title": LESSON["title"]}],
    }
]
