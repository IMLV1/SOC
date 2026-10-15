# ข้อ 07 — Run UI / Event explorer (14 ตุลาคม 2026)

ทำบน codex/step-05-scenarios ที่ HEAD 2cc275f พร้อม working changes ข้อ 06 และ foundations 11–13
ไม่ switch/reset/stash หรือทับงานเดิม ไม่พบ AGENTS.md จากการตรวจ repository
ข้อ 01 มี SRS/OpenAPI/requirement mapping/scaffold/runtime pins/lockfiles อยู่แล้ว
คง training/exam boundary, finish/submit และ decision register ตาม SRS;
learning-path/RAG เป็นแบบออกแบบที่ยังไม่เปิด exam/provider/ingestion จากงาน UI นี้
ไม่มี migration/API route ใหม่ เพราะข้อ 07 ใช้ approved runs/events API ที่มีอยู่

## เปลี่ยนอะไร

- runs/page.tsx: run list/start และ cursor history พร้อมปุ่มโหลดรอบเพิ่มเติม
- runs/[runId]/page.tsx: filters q/source/asset_id/username/src_ip/from/to,
  URL state ของ filters/selected event, pause/resume และ optimistic version conflict handling
- Polling ทุก 2 วินาที, error backoff 4→8→16→30 วินาที, หยุด requests ขณะ document.hidden
- ใช้ cursor เพื่อ drain หน้า events ที่ยังมี next_cursor แล้วกลับไป after_seq โดยไม่ส่งสองค่าในคำขอเดียว
- Filter/session เปลี่ยนล้างข้อมูลเดิม; response เก่าที่ effect ยกเลิกไม่เข้า UI;
  polling ไม่ทับ run version ใหม่หลัง control; 401/403/404/422 หยุด retry อัตโนมัติ
- Request/response/log แสดงใน React text/pre ไม่ render HTML
- run-types.ts ใช้ aliases ของ generated approved API DTOs; generator ส่ง dynamic JSON เป็น Record<string, unknown>
- browser tests เพิ่ม URL filter refresh, cursor, escaped payload, loading/empty/401,
  503 backoff/recovery และ history pagination; runs.spec.ts ยังทดสอบ API/DB จริง

## ผลตรวจจริง

| Check | ผล |
|---|---|
| Local full CI script | soc-ci-ui07 exit 0; build/migrate/API/worker/UI พร้อม; cleanup เฉพาะ project ทดสอบสำเร็จ |
| PostgreSQL | 45 integration tests passed รวม runner/fencing/runs query และ investigation/auth เดิม |
| HTTP smoke | 3 passed |
| Chromium | 9 passed รวม real register/login/start S02/event/pause/refresh/resume และ widths 375/768/1440 |
| UI transport tests | Cursor/after_seq ไม่ปน, escaped script/image ไม่ execute, filters/event คงหลัง refresh, 401, empty, loading, backoff ≥3.8s ก่อน recovery, run cursor append ไม่ซ้ำ |
| Frontend | lint/typecheck/Next standalone build ผ่าน; browser assets leakage 1 test ผ่าน |
| Contract | foundation 13 passed รวม OpenAPI validation/approved drift/draft boundary; generated DTO --check ผ่าน |
| Source/static | generator Ruff ผ่าน; doc links และ git diff --check ผ่าน |

รอบแรก E2E ตรวจ Response หลังล้าง filter ซึ่งล้าง selected event ตาม UI;
แก้ test ให้เลือก event ใหม่หลัง filter reset โดยไม่ลด assertion ของ Request/Response/Log
รอบสุดท้ายทั้งหมดผ่าน ไม่มีการเรียก provider จริงหรือแตะไฟล์ key

## เปิดตรวจ

จาก root ใช้ Docker Linux engine และ secrets local ที่สร้างตามคู่มือ DB:

```powershell
$env:SOC_WEB_PORT='13006'
$env:SOC_API_PORT='18006'
$env:SOC_DB_PORT='55436'
docker compose -p soc-accept06 up --build -d --wait
```

เปิด [run list](http://127.0.0.1:13006/runs), สมัคร/login แล้วเริ่ม S02
ตัวกรอง from/to ใช้ UTC ISO 8601 ที่อยู่ในช่วง run; filter ไม่ตรงได้ empty ไม่ใช่ข้อมูลอนาคต
เปิด event แล้ว refresh เพื่อดู selected event/filter กลับมา; pause/resume ใช้ version ฝั่ง API
เพื่อทดสอบทั้งชุด ใช้ `COMPOSE_PROJECT_NAME=soc-ci-ui07 bash scripts/ci-compose.sh`
CI project เป็นฐานทิ้งได้ และลบเฉพาะ containers/volume ของชื่อนี้เมื่อจบ

## สถานะที่ยังไม่อ้าง

ข้อ 07 ผ่าน local acceptance; **รอยืนยันบน GitHub** สำหรับ working changes นี้
ยังไม่ commit/push/deploy; lockfiles/runtime pins เดิมไม่เปลี่ยน และ prototype ไม่มี diff
ข้อ 08/09 และ 11–13 ที่ยัง pending ไม่ถูกติ๊กจากผล UI นี้
rubric/retake/override-revoke unlock และ provider pipeline ตาม SRS/ไฟล์งานค้างยังแยกอยู่
