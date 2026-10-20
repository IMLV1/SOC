# ข้อ 13 — Knowledge storage / offline ingestion

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ทำบน `codex/step-13-knowledge` ใน worktree แยกจาก `origin/main` (`8c2a978`).
ผู้ใช้อนุมัติ corpus คู่มือทั่วไปสองเรื่องสำหรับ local/mock วันที่ 15 ต.ค. 2026:
อ่าน login และแยก blocked request จาก successful compromise; metadata อยู่ใน
`backend/knowledge/manifest.json`. ไม่มี private truth หรือ scenario answers ใน corpus.

## ใช้งาน

ใช้ Compose ของ worktree นี้กับ project/ports แยกจากระบบเดิม เรียก
`python scripts/init-local.py` ก่อน `docker compose up --build -d` ตาม local-development.md.
ฐานใช้ PostgreSQL 17.11 digest เดิม เพิ่ม vector 0.8.2 ผ่าน `infra/Dockerfile.pgvector`.
Image ต้นทาง extension ถูก pin digest เช่นกัน. Admin bootstrap ติดตั้ง extension
เมื่อ `SOC_INSTALL_VECTOR=yes`; migration_owner ไม่ได้ superuser หรือ CREATE DATABASE.
Managed database ต้องให้ operator ติดตั้ง extension 0.8.2 และ bootstrap schema kb
ก่อน migration wrapper; ไม่เปิด extension หรือ migrate จาก API startup.

Migration ใหม่ `0012_knowledge` ต่อจาก `0011_provider_budget`; ไม่มี dependency/lockfile
เปลี่ยน เพราะใช้ SQL casts ผ่าน asyncpg เดิม ไม่ใช้ vector ORM สร้าง schema อัตโนมัติ.

คำสั่ง operator จาก backend (ใช้ runtime env/password file ของ migration_owner):

```sh
python -m app.knowledge admit knowledge/manifest.json
# จด release UUID ที่คืนมา; Python worker จะ claim ingest_knowledge ตามปกติ
# รอ jobs succeeded แล้ว validate golden ก่อน publish
python -m app.knowledge validate RELEASE_UUID tests/knowledge_queries.json
# held-out เป็น test-only ไม่ใช้ tune threshold หรือใส่ใน index
python -m app.knowledge publish RELEASE_UUID --expected-version 1
python -m app.knowledge revoke DOCUMENT_VERSION_UUID
```

Publisher CLI ไม่มี HTTP endpoint, public upload หรือ arbitrary URL ingestion.
Worker มีสิทธิ์ insert chunks/vectors และเปลี่ยน draft เป็น ready แต่เปลี่ยน active
pointer, แก้ corpus content หรืออ่าน private truth ไม่ได้. Publisher CLI ลดสิทธิ์เป็น NOLOGIN group `knowledge_publisher` ผ่าน SET LOCAL ROLE ก่อนทำงาน;
ไม่มี DDL/private truth grant. `knowledge_ingestor` แยกสิทธิ์เขียน draft ให้ worker
โดยไม่มี publish grant. Operator credential ไม่ mount ใน worker/API.
การออก dedicated operator login แทน migration_owner session เป็น hardening ภายหลัง.

Manifest ตรวจ metadata/hash, duplicate revision, canonical path และ Markdown ที่อยู่ใต้
approved/ เท่านั้น. Admission/job IDs deterministic; version lock + lease fencing
ทำให้ transaction ที่ stale rollback ทั้ง chunks/vectors/status. Partial/revoked/empty
corpus publish ไม่ได้; publish ใช้ expected_version ของ singleton active pointer.
Content, chunks, embeddings, published release และ membership ถูก freeze ผ่าน DB guards.
Revoke ไม่ลบ snapshot แต่ filtered retrieval จะไม่คืน version นั้น รวม pinned release เก่า.

ตั้ง `SOC_KB_ENABLED=true` ใน API environment เมื่อต้องการ pin published release/config
ให้ run ใหม่ (ค่าเริ่มต้น false). API ตรวจ readiness ของ release ใน transaction start_run;
ไม่มี active หรือมี revoked member ให้ KNOWLEDGE_UNAVAILABLE และ rollback run/quota.
Run เดิมไม่ backfill และไม่เปลี่ยน release เมื่อ pointer เปลี่ยน. ขั้นนี้ยังไม่เชื่อม
triage/Ask AI/source drawer; งานนั้นอยู่ข้อ 14 และต้องตรวจ revoke ทุก response projection.

## Embedding / chunking / migration strategy

ใช้เฉพาะ fake-hash-16-v1 dimension 16, cosine exact SQL, deterministic UTF-8 byte splitter
1200 bytes/160 bytes overlap พร้อม heading/byte locator/hash. นี่เป็น byte budget
สำหรับ fake profile ไม่ได้เรียกว่า 500 model tokens และไม่ได้วัด semantic Thai quality.
Retriever จำกัด candidate 12, ผล 5, สูงสุด 2 ต่อ document version และตรวจ published/revoked.
ไม่มี confidence threshold ที่แต่งขึ้นจาก fake similarity; ใช้ทดสอบ integrity เท่านั้น.

เมื่อเลือก real embedding ต้องอนุมัติ model/dimension/tokenizer/งบก่อน: เพิ่ม immutable
profile และตาราง vector(d) ใหม่ด้วย migration, ทำ tokenizer-aware chunking/version ใหม่,
re-embed draft corpus แยก, validate golden/held-out, publish release ใหม่ แล้ว pin เฉพาะ
run ใหม่. ห้ามแก้ dimension in-place หรือผสม vector spaces. เก็บตาราง/profile เก่าจน
references หมดและ retention/rollback policy อนุญาต. ไม่มี real embedding calls ในงานนี้.

## ผลตรวจและข้อจำกัด

ผล local ที่ตรวจแล้วบันทึกด้านล่าง; fake retrieval ชุดเล็กเป็น regression ไม่ใช่
RAG quality benchmark 50 queries ตามข้อ 14. Golden และ held-out labels อยู่เฉพาะ
backend/tests/knowledge_queries.json ไม่ถูก copy ใน runner/knowledge corpus.
GitHub CI ของ branch นี้ยังรอยืนยัน; ไม่มี push/deploy/paid provider จากงานนี้.

สิ่งที่ยังไม่พร้อม: tokenizer ตาม real model, real embeddings/benchmark คุณภาพ,
retention/purge ของ immutable KB snapshots และ RAG response revocation ข้อ 14.
Golden validation ผูก membership snapshot และเป็น integrity gate ของ fake profile ไม่ใช่การอนุมัติคุณภาพโมเดลจริง.


## Local verification (15 ตุลาคม 2026)

- Ruff lint/format และ mypy ผ่าน; API contract ไม่มี route ใหม่ (operator-only lifecycle).
- Backend non-integration/contract: 53 passed; PostgreSQL integration: 58 passed
  ใน soc-ci-knowledge13 (ฐาน soc_test_foundation/tmpfs แยก).
- Test ใหม่ 4 ข้อ: UTF-8/manifest guard, ingestion/publish/revoke/ACL + golden/held-out,
  run pin/dimension/immutable/revoked admission, stale-ingestor rollback.
- Golden 2 และ held-out 2 queries ไทย/อังกฤษตรวจอันดับแรกกับ fake profile เท่านั้น.
- Full Compose/browser pipeline และผลของ GitHub ต้องดูสถานะรอบล่าสุด ไม่ใช้ผลเก่าแทน.
- Extension prerequisites และ roles ตรวจผ่านฐานจริง; ไม่มี real embedding call.


Full local Compose pipeline `soc-ci-knowledge13-full` exit 0: PostgreSQL 58,
HTTP smoke 3, Chromium 11 passed; preview-only case 1 skipped ตาม auth_only flag
ที่ไม่เปิดใน training CI. Next.js production build และ worker/evaluator readiness ผ่าน.
หลังเพิ่ม publisher group/ingestion byte cap/manifest content hash ตรวจ tests ข้อ 13 ซ้ำ.
รันซ้ำเต็มชุดด้วย `COMPOSE_PROJECT_NAME=soc-ci-knowledge13-check bash scripts/ci-compose.sh`.
CI test image รวม tests ใหม่ผ่าน markers เดิม ไม่มี network/provider call ใน tests.

Fake ingestion จำกัด 20 documents, 120KB ต่อ document และ 1MB รวมต่อ admission;
ไม่หัก logical AI quota ผู้เรียนและไม่มีเงิน/usage ภายนอก. Real embedding component
reservation/rate card ต้องทำเมื่ออนุมัติ provider/model/งบและไม่ใช้ fake budget แทน.
หากเปลี่ยน splitter ให้สร้าง document revisions/chunk set ใหม่ควบคู่ profile ใหม่;
ไม่เปลี่ยน ordinal/content ของ chunks ที่ release เก่าอ้าง.


Final targeted acceptance หลัง publisher PUBLIC-USAGE grant fix: 4 passed.
Public schema grants ทำใน admin bootstrap เท่านั้น; migration_owner มี USAGE แต่ไม่มี
สิทธิ์ grant ต่อ จึงไม่ให้ migration แอบอ้างว่า grant public schema สำเร็จ.
Ruff lint/format และ mypy ตรวจซ้ำผ่าน. ข้อ 13 ผ่าน local/mock scope;
GitHub CI ของ branch นี้รอยืนยัน. ไม่อ้าง production/real embedding readiness.
