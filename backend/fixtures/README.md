# Training fixture files

ไฟล์ในโฟลเดอร์นี้เป็นข้อมูลฝึกสำหรับ backend ไม่ใช่ไฟล์สาธารณะหรือข้อมูลใน browser. Catalog บอก scenario ที่เปิดให้เลือก, event files เป็นข้อมูลที่ runner ปล่อยตามเวลา และ ground truth ใช้เฉพาะ evaluator. อ่านข้อจำกัดด้านล่างก่อนเพิ่มหรือแก้ fixture.

`catalog.json` is seed input, not a public asset. Only S02 v1 is enabled initially.
S01–S05 share schema v1 and include routine traffic; complete detector acceptance
belongs to step 08. No fixture is copied from the browser prototype.

`events/training/` contains future schedules for the runner only. Keys are opaque
within each fixture; log records contain observations, not outcome labels.
`ground-truth/training.json` contains incident groups and evidence references for
the evaluator. It is not an exam rubric, score or learner feedback policy.

Public demo uses the separate benign snapshot in app/demo.py. Exam cases, if
added, must stay in a separate restricted bank and must never enter the training
catalog or API. Check the current exam policy and checklist before changing fixtures.

Container base/API: no fixture files. Runner: training events only. Seed/test
targets: restricted catalog/truth inputs. Do not deploy the seed/test image as an
API or worker. No static mount, retrieval indexing or frontend imports are allowed.

Seed canonical hash: SHA-256 of UTF-8 JSON, sorted keys, compact separators,
ensure_ascii=False, Pydantic v1-format defaults included. Existing versions are
immutable; seed conflicts abort the whole transaction instead of updating data.
Introduce new UUID/version files for revisions; keep old versions for replay.
