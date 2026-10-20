# ผล agent self-review ข้อ 14

> **หมายเหตุสถานะปัจจุบัน:** การกล่าวถึง Gemini ในเอกสารนี้เป็นข้อมูลย้อนหลัง/หลักฐานของ implementation ก่อนเลือก Dify ไม่ใช่คำสั่งให้เปิดใช้หรือสถานะ provider ปัจจุบัน; repository ต้องใช้ Dify API เท่านั้น และ runtime ยังปิดจน integration ผ่านการตรวจรับ

> **หมายเหตุ:** ไฟล์นี้เป็นรายงานย้อนหลัง ผลตรวจใช้ได้กับวันที่, commit และ environment ที่ระบุในเนื้อหาเท่านั้น ไม่ใช่สถานะล่าสุดของ repository และไม่ยืนยัน deployment ปัจจุบัน ให้ดู [checklist ล่าสุด](implementation-checklist.md) ประกอบ


ผู้ตรวจ: Codex ซึ่งเป็นผู้เขียน implementation และชุด labels เริ่มต้นด้วย ผู้ใช้อนุญาตให้ตรวจเบื้องต้น ผลนี้เป็น **agent self-review เท่านั้น ไม่ใช่ independent human review** และไม่มีการเปลี่ยนช่อง human approval หรือผล provider เดิม

ตรวจแบบ offline จาก frozen artifacts ไม่เรียก Gemini เพิ่ม ไม่ปรับ threshold ไม่แก้คำตอบย้อนหลัง ไม่ commit/push/deploy

## ขอบเขตและวิธีตัดสิน

อ่าน relevance 100 คำถาม: baseline v1 50 และ retrieval v2 50 พร้อมคู่มือ immutable 2 เรื่อง; ตรวจ sampled claims 57 รายการจากคำตอบสำเร็จ 40 รายการ ตาม sample เดิม ไม่มีการสุ่มใหม่เพื่อเลือกผลดี

- แหล่งที่เกี่ยวข้องต้องช่วยตอบสาระสำคัญของคำถามจริง ไม่ใช่เพียงมีคำเหมือนกัน คำถามทั่วไปนอก corpus ไม่มี relevant chunk
- บางคำถามตอบได้เพียงบางส่วน เช่น ชื่อ timestamp/response fields หรือขั้นตอนยืนยันกับเจ้าของบัญชี คู่มือให้หลักการแต่ไม่มีรายละเอียดครบ ระบุข้อจำกัดไว้ในเหตุผลของแต่ละ label; answerable ใน self-review หมายถึง corpus ช่วยตอบอย่างมีขอบเขต ไม่ใช่มีรายละเอียดทุกข้อ
- Claim ต้องรองรับครบทั้งข้อความด้วย event/knowledge ที่อ้างจาก context ของ operation นั้น ถ้ารองรับได้เพียงบางส่วนให้นับไม่รองรับ แม้หลักการนั้นอาจถูกต้องทั่วไป
- คำว่า denied request is not successful compromise ตีความจำกัดที่คำขอที่ถูกปฏิเสธ ไม่ใช่ยืนยันว่าทั้งระบบหรือเหตุการณ์อื่นไม่มี compromise; ประโยคประเภทนี้ควรให้คนตรวจทบทวนความกำกวมอีกครั้ง
- ตรวจ source hashes และ refs เป็น subset ของ context จริงต่อ operation แล้ว Citation ID ที่มีจริงไม่รับประกัน semantic support

## ผล

| Sample | รองรับ | อัตรา |
|---|---:|---:|
| EN no-RAG | 8/10 | 80.00% |
| EN RAG | 17/17 | 100.00% |
| กลุ่มคำถาม TH no-RAG | 10/11 | 90.91% |
| กลุ่มคำถาม TH RAG | 18/19 | 94.74% |
| รวม | 53/57 | 92.98% |

RAG รวม 35/36=97.22%; no-RAG รวม 18/21=85.71% ตัวเลขนี้เป็น self-review ของ sampled claims จากคำตอบสำเร็จเท่านั้น ไม่ใช่ success rate ของทุกคำถามหรือหลักฐานเชิงสถิติว่า RAG ดีกว่าทั่วไป 4 invalid outputs และ 1 provider failure ยังเป็น failures ใน baseline เดิม ไม่ถูกตัดให้กลายเป็น passed outcomes

Retrieval v2 จาก labels ที่ agent ตรวจ: EN Recall@5=1.00/MRR=0.975, TH Recall@5=0.95/MRR=0.95; คำถามนอกขอบเขต no-match 5/5 ต่อภาษา มี miss จริงที่ `th-authentication-03` (“การลงชื่อเข้าใช้ผ่านแล้วยังมีเรื่องใดที่สรุปไม่ได้”) ซึ่งควรเกี่ยวข้องกับ authentication แต่ไม่พบผล ไม่แก้ label เพื่อลบ miss

Corpus มีเพียงสอง chunks ทำให้ Recall@5 ชุดนี้ทดสอบ threshold/no-match มากกว่าการจัดอันดับในคลังใหญ่ ห้ามสรุปว่าได้คุณภาพเดียวกันกับ corpus กว้าง

## Claims ที่รองรับไม่ครบ

| ID | Operation | ข้อพบและเหตุผล |
|---|---|---|
| C001 | `rag14:held-v1:19:no_rag` | event แสดง denial/403 ได้ แต่ไม่มีหลักฐานรองรับคำแนะนำทั่วไปว่า checking responses/subsequent logs is necessary ซึ่งถูกใส่เป็น observation และไม่มี knowledge citation |
| C003 | `rag14:held-v1:4:no_rag` | event ไม่มี authentication event จึงไม่รองรับการอ้างว่าข้อสรุปเรื่อง authentication ถูก demonstrated by policy denial ทั้งข้อความ แม้หลักการจะสมเหตุผล |
| C029 | `rag14:held-v1:41:no_rag` | ส่วน suspicious URL เป็นหลักการเพิ่มเติมที่ไม่ได้อยู่ใน event หรือ knowledge refs; event นี้ไม่ได้ระบุว่า URL น่าสงสัย จึงรองรับไม่ครบทั้ง claim ที่เป็น observation |
| C056 | `rag14:held-v1:41:rag` | ส่วน blocked request รองรับได้ แต่การกล่าวเพิ่มเรื่อง URL อันตราย/คำขอที่เกี่ยวข้องกับ URL นั้นไม่มีใน event หรือคู่มือที่อ้าง จึงรองรับไม่ครบทั้ง observation |

ข้อพบเหล่านี้หมายถึง cited context รองรับไม่ครบ ไม่ใช่พิสูจน์ว่าทุกประโยคเป็นข้อเท็จจริงเท็จ ควรปรับ prompt/structured semantics ให้แยก observation กับ general guidance และไม่เติมเรื่อง authentication/URL ที่ไม่มีในหลักฐาน แล้วทดสอบด้วย held-out ใหม่ก่อนอ้างว่าดีขึ้น

## ภาษาและข้อจำกัด

พบ 10/30 sampled claims ในกลุ่มคำถามไทยเป็นอังกฤษล้วน (ไม่มีอักษรไทย) ซึ่งเป็นผลตรวจระดับ claim ไม่ใช่ 10 คำตอบ ทั้งคำตอบอาจผสมภาษาได้ และศัพท์เทคนิคภาษาอังกฤษไม่ได้ถูกนับเป็นปัญหาโดยอัตโนมัติ การแบ่ง TH/EN ใน benchmark คือภาษาของ query ไม่ใช่การรับรองภาษาของ output จึงยังต้องตรวจคุณภาพภาษาแยก

ไม่มี full paired answer benchmark บน release v2; grounding ด้านบนมาจาก baseline v1 จึงไม่ใช้แทน grounding ของ v2 โดยปริยาย Unknown usage 6 calls และ GitHub CI ของ changes นี้ยังค้าง ไม่มีการให้ human reviewer หรือเรียก provider เพิ่มจากงาน self-review นี้

## หลักฐานและขั้นต่อไป

- [Agent claims/relevance proposals ของ baseline](artifacts/step-14-agent-claims-review.json): 50 labels และ 57 claims พร้อมเหตุผลรายรายการ
- [Agent relevance proposals ของ v2](artifacts/step-14-agent-retrieval-review.json): 50 labels พร้อม chunk IDs และเหตุผล
- [Machine-readable summary](artifacts/step-14-agent-review-summary.json): source artifact hashes, denominators, unsupported indices และข้อจำกัด
- [คู่มือสำหรับผู้ตรวจอิสระ](step-14-review-guide.md)

ไฟล์ `*.pending.json` ของ human review เดิมยังไม่ถูกแก้ และ scorer ยังคืน pending_review เมื่อประเมิน agent proposals เพราะ independent_of_implementation=false และ approved=false ทุก label ผู้ตรวจสามารถใช้ proposals ลดเวลาการตรวจ แต่ต้องทบทวนหลักฐานและตัดสินเอง ห้ามเปลี่ยนชื่อ agent เป็นผู้ตรวจมนุษย์หรือ flip approval จากผลนี้อัตโนมัติ

เริ่มตรวจทวนที่ C001/C003/C029/C056, คำถามที่ตอบได้เพียงบางส่วน, miss ภาษาไทย และคำตอบไทยที่ใช้ภาษาอังกฤษ จากนั้นประเมิน paired answer benchmark ของ release ใหม่ด้วย labels ที่ผู้ตรวจยืนยัน ดู [ผลตรวจระบบ](step-14-verification.md) ข้อ 14 ยังไม่เสร็จและตรวจรับทั้งหมด

## รายการ sampled claims ครบ 57 ข้อ

Cxxx ใช้ลำดับ 1-based; JSON summary ใช้ indices 0-based ทุกแถวอ้าง operation และ claim_index ใน agent JSON เพื่อเปิดตรวจต้นฉบับได้

| ID | Query language/arm | Claim | Self-review | เหตุผล |
|---|---|---|---|---|
| C001 | en/no_rag | Checking responses and subsequent logs is necessary to verify policy enforcement, as demonstrated by the 403 status response and corresponding request_policy_denied event log. | รองรับไม่ครบ | event แสดง denial/403 ได้ แต่ไม่มีหลักฐานรองรับคำแนะนำทั่วไปว่า checking responses/subsequent logs is necessary ซึ่งถูกใส่เป็น observation และไม่มี knowledge citation |
| C002 | en/no_rag | The request to the restricted path was denied with a 403 status. | รองรับ | event ระบุ path /restricted และ status 403 ตรงกับ claim |
| C003 | en/no_rag | Authentication alone does not prove data access, as demonstrated by the policy denial. | รองรับไม่ครบ | event ไม่มี authentication event จึงไม่รองรับการอ้างว่าข้อสรุปเรื่อง authentication ถูก demonstrated by policy denial ทั้งข้อความ แม้หลักการจะสมเหตุผล |
| C004 | en/no_rag | A denied request is not a successful compromise. | รองรับ | ตีความเฉพาะ denied request ที่ event นี้บันทึก: การกระทำถูกปฏิเสธ ไม่ใช่หลักฐาน successful compromise; ไม่ได้ยืนยันว่าทั้งระบบปลอดภัย |
| C005 | en/no_rag | The available evidence only shows a request policy denial with a 403 status and contains no login success events. | รองรับ | frozen evidence มีเพียง denial/403 ไม่มี login success event; claim จำกัดขอบเขตที่ available evidence |
| C006 | en/no_rag | A denied request is associated with the request_policy_denied event type and status 403. | รองรับ | response.status=403 และ log.event_type=request_policy_denied ตรงกับ claim |
| C007 | en/no_rag | A request to a restricted path resulted in a 403 status and a request_policy_denied event. | รองรับ | request.path=/restricted, response.status=403, log.event_type=request_policy_denied ตรงกัน |
| C008 | en/no_rag | The provided evidence only contains a denied request event and lacks information regarding session creation or what remains unknown after it. | รองรับ | snapshot นี้มี denial event เดียว จึงไม่มีข้อมูล session creation/later activity ตามที่ claim จำกัดขอบเขต |
| C009 | en/no_rag | The provided event log shows a request policy denied response (status 403) from the web source. | รองรับ | source=web, status=403 และ event_type=request_policy_denied ตรงกัน |
| C010 | en/no_rag | A request to /restricted resulted in a policy denial with status 403. | รองรับ | path=/restricted, status=403 และ policy denial อยู่ใน event จริง |
| C011 | en/rag | A successful login records a session, but does not identify who controlled it. | รองรับ | Authentication ระบุตรงตัวว่า successful login records a session but does not identify who controlled it |
| C012 | en/rag | The request resulted in a policy denial status 403. | รองรับ | event มี policy denial และ status 403 โดยตรง |
| C013 | en/rag | A blocked request demonstrates an attempted action and an enforcement response rather than a successful compromise. | รองรับ | event ยืนยัน denial; Blocked รองรับ attempted action/enforcement และไม่สรุป compromise โดยจำกัดที่ request นี้ |
| C014 | en/rag | A denied request is not a successful compromise. | รองรับ | event แสดง denied request; Blocked รองรับว่าการปฏิเสธไม่ใช่หลักฐาน compromise ของ request นี้ ไม่ตีความเป็นทั้งระบบไม่ถูกเจาะ |
| C015 | en/rag | Inspect related events and explain which outcomes remain unknown. | รองรับ | Blocked ระบุ Inspect related events and explain which outcomes remain unknown |
| C016 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, and it does not demonstrate successful compromise. | รองรับ | Blocked ระบุความพยายาม/enforcement และไม่ยืนยัน compromise; event รองรับว่ามี denial จริง |
| C017 | en/rag | Correlate the account, session, asset and time before describing impact. | รองรับ | Authentication ระบุ Correlate the account, session, asset and time before describing impact |
| C018 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, but does not demonstrate successful compromise. | รองรับ | event รองรับ denial และ Blocked รองรับการแยก attempted action/enforcement จาก compromise |
| C019 | en/rag | Correlate the account, session, asset and time before describing impact. | รองรับ | Authentication ระบุ account/session/asset/time ก่อนอธิบาย impact ตรงกับ guidance |
| C020 | en/rag | A blocked request or failed authentication attempt does not demonstrate successful compromise. | รองรับ | Authentication ระบุ failed login เป็น unsuccessful attempt; Blocked ระบุ blocked request ไม่ยืนยัน compromise จึงรองรับคำแนะนำนี้ |
| C021 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, not a successful compromise. | รองรับ | event รองรับ blocked action และ Blocked รองรับ attempted action/enforcement ไม่ใช่หลักฐานผลสำเร็จ |
| C022 | en/rag | Inspect related events and explain which outcomes remain unknown after a policy denial. | รองรับ | Blocked ระบุ inspect related events/unknown outcomes จึงรองรับคำแนะนำหลัง denial |
| C023 | en/rag | A successful login records a session, but does not identify who controlled it. | รองรับ | Authentication ระบุ successful login records session แต่ไม่บอกผู้ควบคุม |
| C024 | en/rag | A successful login records a session, but does not identify who controlled it, and relating sessions to later activity requires correlating the account, session, asset, and time. | รองรับ | Authentication ระบุทั้ง session ไม่บอกตัวผู้ควบคุมและการ correlate account/session/asset/time |
| C025 | en/rag | The available observation is a denied request (status 403) and does not provide session or later activity data. | รองรับ | snapshot มี denial/403 เพียง event เดียว ไม่มี session หรือลำดับกิจกรรมถัดไป |
| C026 | en/rag | Status 403 shows a request policy denial for the GET request to /restricted. | รองรับ | event ระบุ GET /restricted, status 403 และ request_policy_denied โดยตรง |
| C027 | en/rag | A blocked request demonstrates an attempted action and an enforcement response, but it does not demonstrate successful compromise. | รองรับ | Blocked ระบุ attempted action/enforcement และ does not demonstrate successful compromise โดยตรง |
| C028 | th/no_rag | คำขอถูกปฏิเสธด้วยสถานะ 403 ตามบันทึกเหตุการณ์ request_policy_denied | รองรับ | event มี status 403 และ event_type=request_policy_denied ตามข้อความ |
| C029 | th/no_rag | A denied request or the presence of a suspicious URL alone does not prove a compromise. | รองรับไม่ครบ | ส่วน suspicious URL เป็นหลักการเพิ่มเติมที่ไม่ได้อยู่ใน event หรือ knowledge refs; event นี้ไม่ได้ระบุว่า URL น่าสงสัย จึงรองรับไม่ครบทั้ง claim ที่เป็น observation |
| C030 | th/no_rag | The request to /restricted resulted in a status 403 and was denied by policy, indicating that a denied request is not a successful compromise. | รองรับ | event มี /restricted/403/policy denial; ข้อความจำกัดว่าคำขอที่ถูกปฏิเสธนี้ไม่ใช่ successful action ไม่ได้ปฏิเสธ compromise จากเหตุการณ์อื่น |
| C031 | th/no_rag | คำขอ HTTP ถูกปฏิเสธด้วยสถานะ 403 และบันทึกเหตุการณ์ระบุว่าเป็น request_policy_denied | รองรับ | event ระบุ HTTP 403 และ request_policy_denied ตรงกัน |
| C032 | th/no_rag | A denied request is not a successful compromise. | รองรับ | denied request ของ event นี้ไม่ใช่ successful action; ไม่สรุปว่าไม่มี compromise ในบริบทอื่น |
| C033 | th/no_rag | The provided evidence shows a denied request resulting in a policy denial log. | รองรับ | event แสดง denied request และ policy denial ตาม claim |
| C034 | th/no_rag | มีเหตุการณ์การปฏิเสธคำขอเข้าถึงเนื่องจากนโยบายที่เส้นทาง /restricted ได้รับการตอบกลับเป็นสถานะ 403 | รองรับ | path=/restricted, response.status=403 และ request_policy_denied ตรงกับ claim |
| C035 | th/no_rag | มีการบันทึกเหตุการณ์การปฏิเสธคำขอเข้าถึงเนื่องจากนโยบาย (request_policy_denied) | รองรับ | log.event_type=request_policy_denied อยู่จริง |
| C036 | th/no_rag | ระบบบันทึกเหตุการณ์การปฏิเสธคำขอเข้าถึงทรัพยากร (request_policy_denied) | รองรับ | event_type=request_policy_denied รองรับว่ามีบันทึกปฏิเสธคำขอ |
| C037 | th/no_rag | สถานะ 403 บ่งบอกถึงการถูกปฏิเสธนโยบายการขอเข้าถึงตามบันทึกเหตุการณ์ | รองรับ | response.status=403 และ event_type=request_policy_denied รองรับการตีความเฉพาะ event นี้ |
| C038 | th/no_rag | คำขอถูกปฏิเสธตามนโยบาย (403) | รองรับ | response.status=403 และ event_type=request_policy_denied รองรับข้อความ |
| C039 | th/rag | คำขอ HTTP ถูกปฏิเสธที่เส้นทาง /restricted โดยได้ผลลัพธ์สถานะ 403 และมีประเภทเหตุการณ์เป็น request_policy_denied | รองรับ | event ระบุ /restricted, 403 และ request_policy_denied ครบ |
| C040 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามกระทำและมาตรการบังคับใช้ แต่ไม่ยืนยันว่าผู้โจมตีเข้าถึงระบบหรือประสบความสำเร็จในการเจาะระบบ | รองรับ | Blocked รองรับ attempted action/enforcement และไม่ยืนยัน successful compromise |
| C041 | th/rag | A denied request demonstrates an attempted action and an enforcement response, but does not demonstrate successful compromise. | รองรับ | event รองรับ denied action; Blocked รองรับขอบเขต attempts/enforcement ไม่ยืนยัน compromise |
| C042 | th/rag | Inspect related events, explain which outcomes remain unknown, and use generic guides for interpretation rather than making definitive claims about a specific incident. | รองรับ | Blocked ระบุ related events, unknown outcomes และ generic guide ใช้ interpretation ไม่ใช่ factual event claim |
| C043 | th/rag | A successful login records a session, but does not identify who controlled it. | รองรับ | Authentication ระบุ successful login records a session but does not identify who controlled it |
| C044 | th/rag | A blocked request demonstrates an attempted action and an enforcement response, and a denied request is not a successful compromise. | รองรับ | Blocked รองรับ attempts/enforcement ไม่ใช่ successful compromise; event รองรับ denied action จริง |
| C045 | th/rag | A request to /restricted returned a 403 status (request_policy_denied). | รองรับ | path=/restricted, status=403 และ event_type=request_policy_denied ตรงกัน |
| C046 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามดำเนินการและการตอบสนองในการบังคับใช้ โดยไม่ยืนยันว่าการโจมตีสำเร็จ | รองรับ | event รองรับ denial; Blocked รองรับความพยายาม/enforcement ไม่ยืนยันความสำเร็จของโจมตี |
| C047 | th/rag | เมื่อเกิดการเข้าสู่ระบบล้มเหลว ควรตรวจสอบบัญชี session อุปกรณ์ และเวลาก่อนอธิบายผลกระทบ | รองรับ | Authentication ระบุการตรวจ account/session/asset/time ก่อนอธิบาย impact หลัง failed login |
| C048 | th/rag | เหตุการณ์คำขอที่ถูกปฏิเสธแสดงถึงการบังคับใช้นโยบาย แต่ไม่ได้ยืนยันความสำเร็จในการเข้าถึงระบบ | รองรับ | event รองรับ enforcement denial และ Blocked ระบุว่าไม่ยืนยันการเข้าถึงสำเร็จ |
| C049 | th/rag | ต้องตรวจบัญชี session อุปกรณ์ และเวลา เพื่อวิเคราะห์ผลกระทบและความสัมพันธ์ของเหตุการณ์ | รองรับ | Authentication ระบุ account/session/asset/time ก่อนอธิบาย impact และ correlation ตรงกับ guidance |
| C050 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามและการบังคับใช้มาตรการป้องกัน แต่ไม่ยืนยันความสำเร็จของการบุกรุก | รองรับ | Blocked ระบุ attempted action/enforcement และไม่ยืนยัน successful compromise |
| C051 | th/rag | พบเหตุการณ์คำขอที่ถูกปฏิเสธ (request_policy_denied) ที่เส้นทาง /restricted ได้รับสถานะ 403 | รองรับ | event ระบุ request_policy_denied, /restricted และ 403 ครบ |
| C052 | th/rag | สถานะ 403 บันทึกเป็นเหตุการณ์ประเภท request_policy_denied สำหรับเส้นทาง /restricted | รองรับ | event ระบุ /restricted, 403 และ request_policy_denied ครบ |
| C053 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงการบังคับใช้นโยบาย แต่ไม่ยืนยันว่าผู้โจมตีเข้าถึงระบบสำเร็จ | รองรับ | Blocked ระบุ denial/enforcement ไม่ยืนยันการเข้าถึงสำเร็จ ตรงกับ guidance |
| C054 | th/rag | คำขอที่ถูกปฏิเสธแสดงถึงความพยายามกระทำและการตอบสนองเพื่อบังคับใช้นโยบาย แต่ไม่ยืนยันว่าเข้าถึงระบบสำเร็จ | รองรับ | event รองรับ blocked action; Blocked รองรับการตอบสนอง enforcement โดยไม่ยืนยัน success |
| C055 | th/rag | ควรตรวจสอบเหตุการณ์ที่เกี่ยวข้องและระบุข้อมูลหรือผลลัพธ์ที่ยังคงไม่ทราบแน่ชัดเพิ่มเติม | รองรับ | Blocked ให้ตรวจ related events และ unknown outcomes ตรงกับ guidance |
| C056 | th/rag | การพบคำขอที่ถูกปฏิเสธหรือคำขอที่เกี่ยวข้องกับ URL อันตรายแสดงถึงความพยายามและการตอบสนองด้วยการบังคับใช้นโยบาย แต่ไม่ยืนยันว่าการโจมตีประสบความสำเร็จ | รองรับไม่ครบ | ส่วน blocked request รองรับได้ แต่การกล่าวเพิ่มเรื่อง URL อันตราย/คำขอที่เกี่ยวข้องกับ URL นั้นไม่มีใน event หรือคู่มือที่อ้าง จึงรองรับไม่ครบทั้ง observation |
| C057 | th/rag | A blocked request demonstrates an attempted action and an enforcement response, and it does not demonstrate successful compromise. | รองรับ | event รองรับ blocked action และ Blocked ระบุ attempted action/enforcement ไม่ยืนยัน successful compromise |
