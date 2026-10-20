# ข้อ 12 — Free Tier provider controls

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


วันที่ 15 ตุลาคม 2026 · branch `codex/step-12-provider-controls` จาก main หลัง PR #10 merged

## Policy ที่ผู้ใช้ยืนยัน

- Gemini 3.5 Flash-Lite, Free Tier project ไม่มี billing, synthetic training events เท่านั้น
- งบเงินจริง 0 บาท; versioned rate card `gemini-free-2026-10-15-v1` มี input/output rate 0
- global 100 dispatches/วัน UTC, 200,000 tokens/วัน, rolling 5 dispatches/60 วินาที
- quota รายผู้ใช้ 20 logical requests/วันเดิมยังบังคับ; ไม่มี fallback ไป paid model

Migration `0011_provider_budget` เพิ่ม policy และ component call reservations
แยก generation ออกจาก embedding ที่ยังไม่เปิดในข้อ 13. System policy row lock
serialize admission ระหว่าง workers; reserve ด้วย UTF-8 request bytes + framing headroom
4,096 + output cap 2,048 ก่อน network. Actual usage ใช้ provider totalTokenCount
รวมกับ input/output mapping; คืนส่วนต่างเมื่อ usage ยืนยันแล้ว.

Unknown hold ไม่หมดอายุอัตโนมัติและกัน token budget ต่อข้ามวัน. Crash หลัง admission
ไม่ dispatch เจ้าของเดิมซ้ำ. Manual retry สร้าง logical request ใหม่และต้องมี budget
ครอบคลุม unknown hold เดิม. HTTP 429 ไม่มี automatic retry, นับ dispatch ใน RPM/RPD,
คืน token hold เพราะถูกปฏิเสธและตั้ง shared cooldown 60 วินาที.
Timeout/network disconnect เป็น unknown; invalid output ที่มี usage ยังคงคิด usage.
HTTP 5xx ที่ยืนยัน usage ไม่ได้ยังกัน global hold. Provider ล่มไม่ล็อก ticket/note CRUD.

## ผล real call ที่ตรวจย้อนกลับได้

หนึ่งคำขอผ่าน runtime worker secret ใน disposable project `soc-ci-provider12test`:

| Field | ผล |
|---|---|
| arm C | `93200bc1-80d6-417e-b33d-60c3dd520d51` |
| dataset hash | `d2396ba47033098db8a1b2140ca443b231207e3974629b7bb2471ae01c46e714` |
| dispatched UTC | `2026-10-15 05:24:33.053766+00:00` |
| mode/model | real / gemini-3.5-flash-lite |
| input/output/total | 2402 / 1324 / 3726 tokens |
| reserved / settlement | 14313 tokens / consumed 3726 |
| status/error | completed / null |
| cost | 0 ตาม Free Tier/no billing ที่ผู้ใช้ยืนยัน |

A/B รัน detector จริงบน frozen S02 dataset; C คง findings/metrics ของ B
และเพิ่ม structured AI triage ที่ตรวจ citations. S02 นี้มี TP=1, TN=1, FP=0, FN=0;
นี่เป็นผลของ dataset จำลองหนึ่งชุด ไม่ใช่การรับรองคุณภาพทั่วไปหรือ human score.
Mock/injected-provider regression แยกจาก real call ด้านบน. ไม่เก็บ key, upstream bodies
หรือเนื้อหาส่วนตัวในรายงานนี้.
เก็บ metadata และ response hash ใน [หลักฐาน JSON](evidence/step-12-real-call.json).

## เปิดทดสอบและข้อจำกัด

ผลตรวจ local: full `scripts/ci-compose.sh` project `soc-ci-provider12final` exit 0;
PostgreSQL integration 55 passed, backend non-integration/contract 49 passed,
HTTP smoke 3 passed, Chromium E2E 11 passed; Ruff lint/format, mypy,
ESLint, TypeScript, Next production build และ browser asset guard ผ่าน.
New budget/C/reconciliation tests เพิ่มใน CI ผ่าน markers เดิม; ไม่เพิ่ม paid/network job.
มี Starlette/httpx deprecation warning ที่ไม่ทำให้ tests fail.

CI local รอบแรกรับ `.env` ที่เปิด real provider ทำให้ browser test คาด mock แต่ได้ real;
แก้ `ci-compose.sh` ให้ export `SOC_AI_PROVIDER=mock` เสมอ แล้วรันใหม่ผ่านทั้งชุด.
Real-call metadata ด้านบนเป็นของ explicit C smoke แยกจาก CI.

หลังตั้ง local secrets ตาม local-development.md และยืนยัน Free Tier:

```sh
COMPOSE_PROJECT_NAME=soc-ci-provider12 bash scripts/ci-compose.sh
```

API/UI เดิมยังสร้าง A/B และ C unavailable; C จริงเป็น explicit operator command
บน arm ที่ได้รับ assignment และ completed frozen run เท่านั้น:

```sh
docker compose exec worker python -m app.evaluation.real_experiment --arm ARM_UUID
```

คำสั่งนี้มี network effect และใช้ budget; ไม่เรียกใน CI. ดูผลปลอดภัยผ่าน
`tests/report_provider_acceptance.py` เฉพาะฐานทดสอบ หรืออ่าน experiment_arms/provider_calls
ผ่าน operator access. Test fixture setup อยู่ `tests/prepare_provider_acceptance.py`
และปฏิเสธ database ที่ไม่ได้ขึ้นต้น `soc_test_`.

Reconcile เฉพาะข้อมูล usage ที่ยืนยันจาก provider report โดย operator DB owner:

```sh
python -m app.analysis.reconcile --analysis ANALYSIS_UUID --tokens 123 --reason REPORT_REFERENCE
python -m app.analysis.reconcile --arm ARM_UUID --tokens 123 --reason REPORT_REFERENCE
```

ไม่อนุมาน timeout เป็น zero. คำสั่งปฏิเสธ active resource, invalid input และ settlement ซ้ำ;
บันทึก reference/time และปรับ quota ใน transaction เดียว. หาก crash แล้ว C ยัง pending
ให้คง hold ไว้และตรวจ worker ก่อน recovery; ยังไม่มี automatic reconciliation กับ Google.
Experiment C ไม่มีปุ่มเปิด real call สาธารณะ; ไม่เปิด exam/RAG/paid mode/production deployment.
GitHub CI ของ branch นี้ยังรอยืนยัน.
