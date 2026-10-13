export default function Home() {
  return (
    <main>
      <header><span className="brand">SENTINEL / SOC LEARNING LAB</span><span className="badge">ระหว่างพัฒนา · ข้อ 01</span></header>
      <section className="intro" aria-labelledby="title">
        <p className="eyebrow">เรียนรู้จากหลักฐาน</p>
        <h1 id="title">ฝึกคิดอย่างนักวิเคราะห์<br />ความปลอดภัย</h1>
        <p className="lead">เรียนวิธีอ่าน request และ response เชื่อมเหตุการณ์ และอธิบายข้อสรุปจากหลักฐานในระบบจำลอง</p>
        <p className="notice">หน้านี้เป็นโครงเริ่มต้นของระบบ ยังไม่เปิดบัญชี บทเรียน รอบฝึก หรือข้อสอบ และยังไม่มีการเชื่อมฐานข้อมูลหรือ AI</p>
        <a className="health" href="/health/live">ตรวจว่า API ตอบสนอง <span aria-hidden="true">↗</span></a>
      </section>
      <section className="levels" aria-label="เส้นทางการเรียนรู้ที่วางแผนไว้">
        <article><span>01 / เริ่มต้น</span><h2>อ่านหลักฐาน</h2><p>ทำความเข้าใจ Method, Path และผลตอบกลับ โดยแยกความพยายามออกจากผลกระทบ</p></article>
        <article><span>02 / กลาง</span><h2>เชื่อมเหตุการณ์</h2><p>พิจารณาบัญชี session และบริบทจากหลายเหตุการณ์ก่อนสรุป</p></article>
        <article><span>03 / ชำนาญ</span><h2>ตรวจข้อสันนิษฐาน</h2><p>เทียบพฤติกรรมกับ baseline และระบุสิ่งที่ยังพิสูจน์ไม่ได้</p></article>
      </section>
      <footer>ข้อมูลจำลองสำหรับการเรียนรู้ · ยังไม่เปิดให้สอบจริง</footer>
    </main>
  );
}
