# ผลตรวจข้อ 18 — staging deployment และ operations

ตรวจ source tree บน branch `implementation-checklist` ณ 17 ตุลาคม 2026

อัปเดต 18 ต.ค. 2026: Docker Desktop 4.95.0 / Engine 29.8.2 ติดตั้งและทำงานได้; local Compose build, migration, integration **79 passed / 80 deselected**, smoke **3 passed**, E2E **22 passed / 1 skipped**, worker/evaluator readiness checks ผ่าน. นี่เป็น local validation เท่านั้น.

## สิ่งที่มีใน checkout

- `backend/Dockerfile` มี pinned Python base image และ target `api`, `runner`, `seed`, `test`; target เริ่มต้นเป็น API และ fixture แยกจาก API image
- `frontend/Dockerfile` มี pinned Node base image และ standalone Next.js build
- `.github/workflows/ci.yml` ทดสอบ prototype, backend, frontend และ integration; ไม่มี image publish/deploy job
- `scripts/ci-compose.sh` ใช้เฉพาะ `soc-ci-*` isolated Compose project และทำ integration/E2E cleanup; ไม่ใช่ staging deploy/rollback script
- API มี `/health/live` และ `/health/ready`; worker/evaluator มี `--check` command ใน CI harness
- `docs/ci-cd.md` ระบุชัดว่า provider, registry, domain และ environment credentials ยังไม่ถูกเลือก/ตั้งค่า

## ยังไม่ได้ทำหรือยืนยัน

ยังไม่มี staging environment/registry/hosting credentials ที่ยืนยันได้ จึงไม่มี immutable release image digest, deploy/migrate/rollback run, HTTPS acceptance หรือ backup/restore evidence ให้รายงาน

ไม่สร้าง deployment adapter หรือ workflow ที่เดา provider/credentials และไม่ publish/deploy ภายนอก การสร้างไฟล์ deploy ที่ยังไม่ผูกกับ environment จะไม่พิสูจน์ staging acceptance ตาม checklist

## ขั้นตอนที่ต้องทำเมื่อ environment พร้อม

1. เลือก hosting/registry/domain และแยก staging DB/credentials ตามบทบาทใน [ci-cd.md](ci-cd.md).
2. รัน GitHub CI บน SHA ที่จะปล่อย แล้ว build API/worker/web images; เก็บ immutable digests ใน release manifest.
3. รัน migration แบบ one-shot ด้วย migration role, deploy API/worker/web และตรวจ readiness/heartbeat/queue/pgvector.
4. ทำ authenticated smoke flows, HTTPS/cookie/CSRF checks, application rollback drill และ backup restore ไป DB ใหม่; เก็บผลและ SHA/digests.

ข้อ 18 ยังไม่ผ่านและ checklist ยังคง unchecked. ไม่มี external action ในรอบนี้.
