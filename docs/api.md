# SOC Platform — API Contract (Draft)

วันที่: 12 ตุลาคม 2026 · สถานะ: สัญญา API ที่เสนอ **ยังไม่มี endpoint เหล่านี้ให้เรียกจริง**

อ่านร่วมกับ [Architecture](architecture.md) และ [Development plan](development-plan.md) ขั้นถัดไปคือแปลงเป็น `docs/openapi.yaml` ใน Phase 0 และใช้ contract tests ตรวจ implementation

การจัดเก็บข้อมูลและ transaction ของแต่ละ endpoint อยู่ใน [Database design](database.md); checks และการนำ API ขึ้นระบบอยู่ใน [CI/CD design](ci-cd.md)

## 1. ข้อตกลงทั่วไป

- Base path: `/api/v1`; JSON request/response ใช้ `snake_case`
- ID เป็น UUID; ตัวอย่าง `run_id`, `event_id`, `ticket_id` ในตารางหมายถึง UUID ของ resource จริง ไม่ใช่รหัส TKT ที่แสดงใน UI
- เวลาเป็น UTC ISO 8601 เช่น `2026-10-12T10:00:00Z`; `elapsed_ms` คือเวลาจำลอง
- Enum ใช้ lowercase: severity=`low|medium|high|critical`; role=`analyst|instructor`
- Ticket status=`open|investigating|resolved|closed`; disposition=`true_positive|benign_positive|false_positive|undetermined` หรือ null หากยังไม่ประเมิน
- Run status=`created|running|paused|reviewing|completing|completed|failed`
- Analysis status=`queued|running|succeeded|failed|invalid_output|quota_exceeded|timed_out|cancelled`; mode=`mock|real`
- Client ใช้ cookie session (`credentials: include`) ไม่ส่ง user_id เพื่อเลือกเจ้าของข้อมูล และไม่เก็บ session token ใน localStorage
- ทุก mutation รวม register/login ใช้ `X-CSRF-Token` จาก `/auth/csrf` และ Origin ที่ยอมรับ
- ทุก POST/PATCH/DELETE ที่มี JSON ส่ง `Content-Type: application/json`; ไม่รับ unknown fields
- `expected_version` บังคับสำหรับแก้ resource หรือเปลี่ยนสถานะที่มี version; server update แบบ compare-and-swap และเพิ่ม version ใน transaction เดียวกับ audit
- POST สร้าง run/ticket/note, retry analysis และ experiment ต้องมี `Idempotency-Key` (UUID); key เดิมกับ body เดิมคืนผลเดิม, body ต่างคืน 409 ผูก key กับบัญชี+method+path เก็บอย่างน้อย 24 ชั่วโมง รวมช่วงงานยังไม่เสร็จ
- ตรวจสิทธิ์ก่อนดู idempotency cache เสมอ และ reserve key, domain data, audit/jobs แบบ atomic

คำขอที่ไม่มีสิทธิ์ต่อ resource เฉพาะคืน 404 เพื่อลดการเผยว่ามีข้อมูล ส่วนการเข้าหน้า admin ด้วย Analyst คืน 403

### Response envelope

```json
{
  "data": { "id": "6bb5762c-3ff9-4df0-94da-ea1587bb1a7b", "status": "running", "version": 1 },
  "meta": { "request_id": "req_01" }
}
```

List ส่ง `data: []` และ `meta: {request_id, next_cursor}` โดย next_cursor=null เมื่อหมด ใช้ cursor pagination, limit เริ่มต้น 50 สูงสุด 100, sort คงที่ด้วย created_at/id หรือ event_time/id ไม่คำนวณ total แบบแพงทุก request

### Error envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "ต้องเลือกข้อสรุปก่อนปิด Ticket",
    "fields": [{ "field": "disposition", "code": "REQUIRED_FOR_CLOSURE" }]
  },
  "meta": { "request_id": "req_02" }
}
```

| HTTP | Code ตัวอย่าง | ความหมาย |
|---|---|---|
| 400 | BAD_REQUEST | JSON, cursor หรือรูปแบบ query ใช้ไม่ได้ |
| 401 | AUTH_REQUIRED / SESSION_EXPIRED | ไม่มี session ที่ใช้งานได้ |
| 403 | FORBIDDEN / CSRF_INVALID | role ไม่ถูกต้องหรือ CSRF ไม่ผ่าน |
| 404 | NOT_FOUND | ไม่พบ resource หรือไม่มีสิทธิ์เห็น |
| 409 | VERSION_CONFLICT / INVALID_TRANSITION / RUN_READ_ONLY / IDEMPOTENCY_CONFLICT | ข้อมูลถูกแก้ไปแล้วหรือ state ไม่รับคำขอนี้ |
| 413 | PAYLOAD_TOO_LARGE | เกินขนาด request ที่กำหนด |
| 422 | VALIDATION_ERROR | field หรือความสัมพันธ์ของข้อมูลไม่ถูกต้อง |
| 429 | RATE_LIMITED / QUOTA_EXCEEDED | จำกัดความถี่หรือโควตา; มี Retry-After เมื่อระบุเวลารอได้ |
| 503 | SERVICE_UNAVAILABLE | API/DB ไม่พร้อม; AI failure ของงานเบื้องหลังแสดงบน Analysis แทนทำให้ทุก GET ล้มเหลว |

## 2. สิทธิ์และนโยบายการเขียน

| Actor | อ่าน | เขียน |
|---|---|---|
| Guest | auth bootstrap, public scenario catalog, `/demo/*` | register/login เท่านั้น |
| Analyst | `/me` และรอบตนเอง | run controls, ticket/note ของตน และ analysis retry ภายในโควตา |
| Instructor | รอบที่กำกับผ่าน `/admin/*`, audit และ ground truth | บัญชี/โควตา, comments, ticket severity/status พร้อมเหตุผล |
| Worker | internal services ตาม DB role | events/detections/analyses/evaluations; ไม่มี browser endpoint สำหรับเขียนข้อมูลเหล่านี้ |

Instructor ใช้ endpoint ปกติเพื่อฝึกในรอบของตนได้ แต่สิทธิ์ Instructor ไม่ทำให้ใช้ route ของ Analyst เขียน assessment ของผู้อื่นได้ หากกำกับรอบผู้อื่นต้องใช้ `/admin/*`

รอบที่กำกับหมายถึงรอบของสมาชิกที่มี `instructor_assignments` ให้ Instructor คนนั้นตาม [Database design](database.md) การมอบหมายทำผ่าน server provisioning ใน MVP; ไม่มี assignment ให้ปฏิเสธการอ่าน/แก้ resource ของสมาชิกคนนั้นตามกติกา 404 ไม่เปิดสิทธิ์ทุกบัญชีจาก role เพียงอย่างเดียว

`completing/completed/failed` เป็น read-only สำหรับ ticket/note/assessment และ controls นอกเหนือจากการเริ่มรอบใหม่; Instructor เพิ่ม comment ได้จนถึง retention expiry แต่แก้ severity/status ได้เฉพาะก่อน completing

## 3. Authentication และบัญชี

| Method | Endpoint | Input | ผลสำเร็จ |
|---|---|---|---|
| GET | `/auth/csrf` | — | 200 token ผูก pre-auth/session cookie; `Cache-Control: no-store` |
| POST | `/auth/register` | email, display_name, password | 201 user role=analyst; ยังไม่ login อัตโนมัติ |
| POST | `/auth/login` | email, password | 200 user + csrf_token ใหม่; Set-Cookie session ใหม่ |
| GET | `/auth/session` | cookie | 200 user, expires_at, csrf_token หรือ 401 |
| POST | `/auth/logout` | `{}` | 204 revoke session และล้าง cookie; session ที่หมดแล้ว logout ซ้ำได้ |
| GET | `/me` | cookie | 200 id, display_name, email, role, status |
| GET | `/me/quota` | cookie | 200 run/AI limit, used, reserved, reset_at |

Validation ที่เสนอ: display_name 1–60 chars หลัง trim, email ไม่เกิน 254 chars และ normalize ก่อน unique check, password 12–128 chars ไม่ trim หรือเก็บ plaintext; registration/login failure ไม่บอกว่า email ใดมีบัญชีอยู่ ห้าม client ส่ง role, status หรือ quota ใน register

Logout ซ้ำที่ session หมดแล้วไม่มีผลแก้ข้อมูลอื่น ตรวจ Origin และล้าง cookie ได้ ส่วน logout ของ session ที่ยัง active ต้องตรวจ CSRF ตามปกติ

## 4. Public demo และ scenario catalog

| Method | Endpoint | ผลลัพธ์ |
|---|---|---|
| GET | `/scenarios` | public metadata: id, version, title, difficulty, duration_ms, learning_objectives |
| GET | `/demo/overview` | counters และสถานะรอบตัวอย่าง |
| GET | `/demo/events` | released/redacted events แบบแบ่งหน้า ใช้ตัวกรองเดียวกับ Event explorer |
| GET | `/demo/events/{event_id}` | event หลักฐานตัวอย่าง |
| GET | `/demo/alerts` | alerts ตัวอย่างและ linked ticket IDs |
| GET | `/demo/tickets` | tickets ตัวอย่าง |
| GET | `/demo/tickets/{ticket_id}` | detail, evidence, mock/real mode และ human assessment ตัวอย่าง |
| GET | `/demo/evaluation` | ผลของรอบตัวอย่างที่เผยแพร่แล้ว ระบุข้อมูลตัวอย่างชัดเจน |

Demo เป็น seed snapshot ที่แยกจากรอบของสมาชิก ไม่เปิด route mutation และ GET ไม่ trigger งาน AI ใด ๆ Catalog ไม่ส่ง fixture schedule, private label หรือคำตอบของโจทย์

## 5. Simulation runs

| Method | Endpoint | Input / Query | ผลสำเร็จ |
|---|---|---|---|
| GET | `/runs` | status?, cursor?, limit? | 200 เฉพาะรอบของผู้ใช้ |
| POST | `/runs` | scenario_ids[1..5], seed? | 201 สร้างและเริ่ม running พร้อม version; ยึด scenario versions ตอนสร้าง |
| GET | `/runs/{run_id}` | — | 200 สถานะ เวลา version และ quota/expiry metadata |
| GET | `/runs/{run_id}/overview` | — | 200 counters, histogram, ticket severity และ analysis statuses |
| POST | `/runs/{run_id}/pause` | expected_version | 200 paused, elapsed_ms และ version ใหม่ |
| POST | `/runs/{run_id}/resume` | expected_version | 200 running และ version ใหม่ |
| POST | `/runs/{run_id}/finish` | expected_version | 202 completing + evaluation_url |
| GET | `/runs/{run_id}/audit` | cursor?, limit?, entity_id? | 200 append-only change history |
| GET | `/runs/{run_id}/export` | — | 200 downloadable JSON เมื่อ completed; ก่อนนั้น 409 |

POST /runs เป็นธุรกรรมที่สร้าง created แล้วเปลี่ยนเป็น running ภายใน transaction; ภายนอกเห็น running หรือ error ไม่ต้องมี endpoint start เพิ่ม `scenario_ids` ต้องไม่ซ้ำและอยู่ใน catalog ที่เปิดใช้ seed เป็นจำนวนเต็ม 0–2^31−1 หรือ server สุ่มและส่งกลับ

ตัวอย่างสร้างรอบ:

```http
POST /api/v1/runs
Content-Type: application/json
X-CSRF-Token: <token>
Idempotency-Key: 85189b13-6905-4625-a497-af60b3c09c2c
```

```json
{
  "scenario_ids": ["e1c99650-03ec-4e97-bf1c-a71b33e4c111"],
  "seed": 42
}
```

```json
{
  "data": {
    "id": "6bb5762c-3ff9-4df0-94da-ea1587bb1a7b",
    "status": "running",
    "version": 1,
    "elapsed_ms": 0,
    "duration_ms": 75000,
    "server_time": "2026-10-12T10:00:00Z",
    "expires_at": "2026-11-11T10:00:00Z",
    "seed": 42,
    "analysis_mode": "mock"
  },
  "meta": { "request_id": "req_03" }
}
```

duration มาจาก scenario version ไม่รับจาก browser ค่า 75 วินาทีเป็นตัวอย่าง seed เดิม ไม่บังคับว่าทุก scenario ต้องเท่านี้ Pause/resume ผิดสถานะคืน 409; finish ซ้ำขณะ completing/completed คืน resource เดิมโดยไม่เริ่ม evaluation ซ้ำและไม่ต้องตรง version เก่า แต่ยังตรวจเจ้าของและ CSRF

## 6. Events และ alerts

| Method | Endpoint | Query / Response |
|---|---|---|
| GET | `/runs/{run_id}/events` | q?, from?, to?, source?, asset_id?, username?, src_ip?, after_seq?, cursor?, limit? |
| GET | `/runs/{run_id}/events/{event_id}` | request, response, raw log ที่ redact แล้ว พร้อม event_time และ ingested_at |
| GET | `/runs/{run_id}/alerts` | severity?, detector_type?, cursor?, limit?; คืน rule/anomaly explanation และ ticket refs |
| GET | `/runs/{run_id}/alerts/{alert_id}` | detection version, correlation reason, evidence refs และ linked ticket |

`from` inclusive, `to` exclusive ใช้ event_time UTC และ from < to; q ความยาว <=200 chars; จำกัดช่วง query ให้ไม่เกินช่วงรอบ แหล่ง source เป็น enum ของ fixture ที่ประกาศไว้ ไม่ปล่อย SQL expression จาก client

`after_seq` เป็น sequence ของการ ingest ไม่ใช่ event_time เพื่อรองรับ log ที่มาช้า หากเลือกโหมดนี้ให้เรียง release_seq ASC และห้ามใช้ร่วมกับ cursor ที่มาจากโหมดอื่น หลังใช้ cursor แล้วต้องคง filters เดิม

ตัวอย่าง event resource:

```json
{
  "id": "b485f73a-e5c6-4b62-905b-43312b21d924",
  "run_id": "6bb5762c-3ff9-4df0-94da-ea1587bb1a7b",
  "release_seq": 3,
  "event_time": "2026-10-12T10:00:29Z",
  "ingested_at": "2026-10-12T10:00:30Z",
  "source": "authentication",
  "asset_id": "AUTH-01",
  "username": "finance.user",
  "src_ip": "198.51.100.20",
  "request": { "method": "POST", "path": "/auth/login", "authorization": "[REDACTED]" },
  "response": { "status": 200 },
  "log": { "event_type": "session_created", "session_id": "SES-041" }
}
```

ไม่มี POST/PATCH/DELETE event หรือ alert สำหรับ browser รหัส session ในหลักฐานเป็น session สมมติ ไม่ใช่ cookie session ของแอป

## 7. Ticket CRUD และ assessment

| Method | Endpoint | Input / Query | ผลสำเร็จ |
|---|---|---|---|
| GET | `/runs/{run_id}/tickets` | q?, severity?, status?, disposition?, deleted=exclude/only/include, cursor?, limit? | 200 list |
| POST | `/runs/{run_id}/tickets` | title, severity, evidence_ids, reason | 201 manual ticket, open, version=1 |
| GET | `/runs/{run_id}/tickets/{ticket_id}` | — | 200 detail รวม deleted flag และ latest assessment |
| PATCH | `/runs/{run_id}/tickets/{ticket_id}` | expected_version, reason, title?, severity?, status?, disposition? | 200 ticket พร้อม assessment revision เมื่อข้อสรุปเปลี่ยน |
| DELETE | `/runs/{run_id}/tickets/{ticket_id}` | expected_version, reason | 200 soft-deleted resource + version ใหม่ |
| POST | `/runs/{run_id}/tickets/{ticket_id}/restore` | expected_version, reason | 200 restored resource + version ใหม่ |
| GET | `/runs/{run_id}/tickets/{ticket_id}/timeline` | cursor?, limit? | 200 released evidence + investigation history |
| GET | `/runs/{run_id}/tickets/{ticket_id}/assessments` | cursor?, limit? | 200 assessment revisions |

DELETE ใน contract นี้รับ JSON body ที่ระบุข้างต้น ให้ API client ส่ง body โดยตรงและทดสอบผ่าน reverse proxy จริง ไม่ใช้ query string เพื่อส่งเหตุผลการลบ

Validation:

- title 1–120 chars; reason 1–2,000 chars หลัง trim
- evidence_ids ตอนสร้าง 1–50 UUID ไม่ซ้ำ ต้องเป็น event ที่ปล่อยแล้วใน run เดียวกัน
- list ค่าเริ่มต้น deleted=exclude; detail อ่านรายการลบได้สำหรับเจ้าของเพื่อกู้คืน แต่ PATCH/note mutation ถูกปฏิเสธจน restore
- ทุกการแก้ assessment บันทึก revision และ audit; ห้ามแก้ AI result ผ่าน PATCH ticket
- ไม่รับ owner_user_id, run_id, origin, correlation_key หรือ evidence ที่อยู่คนละรอบจาก payload
- completed เป็น read-only ตาม architecture; การ restore ใช้ได้ก่อน completing และก่อนหมด retention

สถานะที่อนุญาต:

```text
open → investigating → resolved → closed
resolved → investigating
closed → investigating
```

อัปเดตโดยคงสถานะเดิมได้ แต่ต้องมีเหตุผล resolved/closed ต้องมี disposition และเหตุผล รวมถึง undetermined ที่ต้องระบุสิ่งที่ขาด ห้ามถือ undetermined ว่าปลอดภัย

ตัวอย่างประเมิน ticket ที่กำลัง investigating:

```json
{
  "expected_version": 3,
  "severity": "high",
  "status": "resolved",
  "disposition": "true_positive",
  "reason": "พบ session สำเร็จและการอ่านข้อมูลตามหลักฐานที่เชื่อมกับเคส เจ้าของบัญชีปฏิเสธกิจกรรม"
}
```

Human severity override ไม่ถูก AI เขียนทับ ส่วน detector severity และ AI suggested_severity เก็บแยกให้เปรียบเทียบได้

## 8. Investigation notes

เส้นทางฐาน `T=/runs/{run_id}/tickets/{ticket_id}`

| Method | Endpoint | Input / Query | ผลสำเร็จ |
|---|---|---|---|
| GET | `T/notes` | deleted?, cursor?, limit? | 200 notes ที่มีสิทธิ์อ่าน |
| POST | `T/notes` | body, evidence_ids[] | 201 note owner=current user |
| PATCH | `T/notes/{note_id}` | expected_version, body, evidence_ids[], reason | 200 note + version ใหม่ |
| DELETE | `T/notes/{note_id}` | expected_version, reason | 200 soft-deleted note |
| POST | `T/notes/{note_id}/restore` | expected_version, reason | 200 restored note |
| GET | `T/notes/{note_id}/versions` | cursor?, limit? | 200 immutable previous versions |

body 1–2,000 chars; evidence_ids 0–50 UUID ที่อยู่ใน ticket/run นี้ ผู้เขียนเท่านั้นแก้/ลบ/restore note ของตนได้ Instructor ใช้ comment route แยก ไม่ได้สิทธิ์แก้ note นักเรียน ข้อความและ raw log แสดงแบบ escaped text ไม่ render HTML ที่ผู้ใช้ส่งมา

## 9. Analysis API

| Method | Endpoint | Input / Response |
|---|---|---|
| GET | `/runs/{run_id}/analyses` | status?, ticket_id?, cursor?, limit? |
| GET | `/runs/{run_id}/analyses/{analysis_id}` | mode, status, model/prompt version, evidence refs, result, usage, error |
| POST | `/runs/{run_id}/analyses/{analysis_id}/retry` | expected_version; 202 analysis_id ใหม่ + status=queued |

Retry ได้เฉพาะ failed/timed_out/invalid_output/quota_exceeded ก่อน completing และต้อง reserve quota ได้ ไม่รับ custom prompt, arbitrary URL หรือ model/API key จาก browser ผลเดิมยังอยู่ งานใหม่อ้าง retry_of เดิมและ snapshot เดิม หากมีหลักฐานใหม่ให้ detection pipeline สร้าง revision ใหม่แทน

ตัวอย่าง `result` เมื่อ succeeded:

```json
{
  "summary": "พบการเข้าสู่ระบบสำเร็จหลังความพยายามหลายครั้ง ต้องตรวจสอบเจ้าของ session",
  "hypotheses": [{ "text": "อาจมีการใช้บัญชีโดยไม่ได้รับอนุญาต", "evidence_refs": ["b485f73a-e5c6-4b62-905b-43312b21d924"] }],
  "evidence_refs": ["b485f73a-e5c6-4b62-905b-43312b21d924"],
  "observed_impact": "มี session ที่ยืนยันตัวตนสำเร็จ",
  "potential_impact": "อาจเข้าถึงข้อมูลตามสิทธิ์บัญชี ยังไม่ยืนยัน",
  "suggested_severity": { "level": "medium", "reason": "ยังไม่มีหลักฐานการอ่านข้อมูล" },
  "confidence": { "level": "medium", "reason": "ข้อมูลกิจกรรมหลัง login ยังไม่ครบ" },
  "unknowns": ["ผู้ใช้งานเป็นเจ้าของบัญชีหรือไม่"],
  "recommended_checks": ["ตรวจ activity ของ session และยืนยันกับเจ้าของบัญชี"]
}
```

ถ้า AI ล้มเหลว GET ยังคืน 200 resource ที่ status=failed และ result=null พร้อม error_code ที่ไม่เปิดเผย secret; ไม่คืนผลสำเร็จว่างที่ทำให้ UI ตีความว่าไม่มีภัย ค่า usage/cost ที่ไม่ทราบเป็น null

## 10. Evaluation และ experiments

| Method | Endpoint | ผลลัพธ์ |
|---|---|---|
| GET | `/runs/{run_id}/evaluation` | ก่อน finish:409 EVALUATION_LOCKED; completing:202 pending; completed:200 snapshot |
| GET | `/runs/{run_id}/ground-truth` | 200 เฉพาะเจ้าของรอบที่ completed; ก่อนนั้น 409 GROUND_TRUTH_LOCKED |
| POST | `/admin/experiments` | dataset_run_id, modes=[A,B,C], config_versions; 202 batch ID |
| GET | `/admin/experiments/{experiment_id}` | 200 arm statuses, dataset hash, versions, metrics และข้อจำกัด |

Experiment source ต้อง completed และมีสิทธิ์กำกับ ห้ามดึงคำตอบผู้ฝึกหรือเฉลยเข้าข้อมูล detector/AI ใช้ complete dataset หรือระบุ truncated=true ชัดเจนรอบที่จบก่อน schedule ครบ งาน C จริงที่ยังไม่ต่อ provider ต้องเป็น unavailable ไม่ใช้ mock ทดแทนใน benchmark

Evaluation payload ประกอบด้วย:

- run_id, revision, status, released_event_count, release_cutoff, assessment_cutoff, truncated
- scenario_results: human_answer, ground_truth_label, evidence_complete, correct, ticket_deleted
- detection_metrics: unit=`incident_group`, tp/fp/fn/tn, precision, recall, null_reason
- human_metrics: correct_count, total_groups, undetermined_count; แยก manual tickets ที่ยังไม่จับคู่กับ incident
- ai: mode, succeeded/failed counts, measured_usage, measured_cost หรือ null
- versions และ dataset_hash เพื่อทำซ้ำได้

Human score และ detector metrics ใช้คนละแหล่งข้อมูล Deleted ticket ไม่ทำให้ incident หายจากผล รายละเอียดการนับและเหตุผลที่ B/C อาจมี detection metrics เท่ากันอยู่ใน [Architecture §11](architecture.md#11-การประเมิน-abc)

## 11. Admin / Instructor

| Method | Endpoint | Input / Query | ผลสำเร็จ |
|---|---|---|---|
| GET | `/admin/users` | q?, status?, cursor?, limit? | 200 safe user fields |
| PATCH | `/admin/users/{user_id}` | expected_version, status=active/disabled, reason | 200; disabled revoke sessions ใน transaction เดียว |
| PATCH | `/admin/users/{user_id}/quota` | expected_version, daily_runs, daily_ai_requests, reason | 200; ไม่ reset การใช้เดิม |
| GET | `/admin/runs` | owner_user_id?, status?, cursor?, limit? | 200 supervised runs |
| GET | `/admin/runs/{run_id}` | — | 200 run metadata |
| GET | `/admin/runs/{run_id}/events` | filters เหมือน events ปกติ | 200 released evidence เท่านั้น |
| GET | `/admin/runs/{run_id}/events/{event_id}` | — | 200 redacted event detail |
| GET | `/admin/runs/{run_id}/tickets` | filters เหมือน tickets ปกติ | 200 tickets |
| GET | `/admin/runs/{run_id}/tickets/{ticket_id}` | — | 200 assessment/notes/evidence/analysis ที่ใช้ review |
| PATCH | `/admin/runs/{run_id}/tickets/{ticket_id}` | expected_version, severity?, status?, reason | 200; ไม่รับ title/disposition/assessment/note |
| GET | `/admin/runs/{run_id}/ground-truth` | — | 200 แม้รอบยังไม่จบ ผ่าน privileged handler และ audit การอ่าน |
| GET | `/admin/runs/{run_id}/evaluation` | — | status contract เหมือน evaluation ปกติ |
| GET | `/admin/runs/{run_id}/audit` | cursor?, limit? | 200 review/change history |
| GET | `/admin/runs/{run_id}/comments` | cursor?, limit? | 200 instructor comments |
| POST | `/admin/runs/{run_id}/comments` | body 1–2,000 chars | 201 comment พร้อม author |

อ่าน review data ของผู้เรียนผ่าน Instructor routes ให้มี access audit ห้ามเปลี่ยน role ผ่าน user PATCH ส่วนการ bootstrap Instructor ใช้คำสั่งฝั่ง server ที่ทีมทำใน Phase 1 และไม่เปิด public API

การปรับ status ของ Instructor ใช้ transition validation เดียวกับ Analyst หากต้อง resolved/closed ต้องมี assessment ของผู้เรียนอยู่แล้ว Instructor ใส่เหตุผลแทนคำตอบของผู้เรียนไม่ได้ ไม่อนุญาตให้ปิดบัญชี Instructor คนสุดท้ายหรือปิดบัญชีตัวเองผ่านหน้าจอนี้

## 12. Internal jobs และ health checks

ไม่มี public endpoint สำหรับ ingest fixture, run detector, เขียนผล AI หรือคำนวณ metrics ตามค่าที่ client ส่ง งานทั้งหมดถูก enqueue โดย service ที่ตรวจสิทธิ์แล้ว

| Job | Dedupe scope | Output |
|---|---|---|
| release_events | run_id + release cursor batch | events + detection jobs |
| detect_events | run_id + detector version + batch hash | detections, alerts, linked ticket |
| analyze_evidence | run_id + evidence hash + model/prompt + logical request | analysis revision |
| finalize_run | run_id + completion revision | assessment snapshot + evaluation |
| experiment_arm | experiment_id + A/B/C | actual detector/AI output + metrics |
| purge_expired | resource + expiry revision | retention cleanup report |

`GET /health/live` คืน 200 เมื่อ API process ตอบได้; `GET /health/ready` คืน 200 เมื่อ DB/migrations พร้อม หรือ 503 เมื่อไม่พร้อม ทั้งสองอยู่นอก `/api/v1` และไม่เผย credentials, provider config หรือข้อมูลผู้ใช้ Worker มี heartbeat ที่ระบบ monitoring ตรวจได้โดยไม่เผย admin endpoint สู่ Guest

## 13. Frontend integration

1. เปิดหน้า: GET `/auth/session`; ถ้า 401 ใช้ `/demo/*` และ public catalog
2. ก่อน auth mutation: GET `/auth/csrf`; login แล้วใช้ csrf_token ใหม่
3. เริ่มรอบ: GET `/me/quota` เพื่อช่วยแสดง UI แต่ POST `/runs` ต้องตรวจ quota ซ้ำฝั่ง server
4. Poll run/overview ทุก 2 วินาทีขณะ running และใช้ events after_seq ดึง incremental; backoff เมื่อ network error และหยุด polling ที่ไม่จำเป็นเมื่อ tab ซ่อน
5. paused หยุด event polling ได้ แต่ analysis ที่เริ่มแล้วอาจเสร็จจึงยัง refresh analysis ได้; reviewing สืบสวนต่อโดยยังไม่ดึงเฉลย
6. ทุก mutation ใช้ version ล่าสุดและรักษา draft เมื่อเจอ 409 ให้ผู้ใช้โหลดข้อมูลใหม่ก่อนยืนยันอีกครั้ง
7. finish ได้ 202 แล้ว poll evaluation จน completed; ห้ามแสดงคะแนน 0 แทน pending
8. 401 กลับ Login โดยไม่ลบ history ที่ server; 403/404/429 แสดงสิทธิ์/ไม่พบ/โควตาตามจริง

## 14. External integrations ที่ยังต้องเลือก

Frontend ใช้ API ข้างต้นเท่านั้น ส่วน backend มี AI provider API เป็น external dependency ที่ต้องเพิ่มใน Phase 4 ต้องบันทึก provider URL/SDK/model, authentication header, structured-output schema, timeout และ usage mapping หลังตัดสินใจแล้ว

Database เชื่อมผ่าน PostgreSQL driver ไม่ใช่ browser REST API; hosting health/backup ใช้ระบบของผู้ให้บริการที่เลือก ไม่ต้องเพิ่ม mail/SIEM/EDR API ใน MVP นี้
