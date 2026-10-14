"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { read } from "../../../../../../../../lib/api";

type Version = { version: number; body: string; change_kind: string; reason: string | null;
  evidence_ids: string[]; actor_user_id: string; created_at: string };

export default function NoteVersionsPage() {
  const { runId, ticketId, noteId } = useParams<{ runId: string; ticketId: string; noteId: string }>();
  const [versions, setVersions] = useState<Version[]>([]);
  const [message, setMessage] = useState("กำลังโหลด…");
  useEffect(() => {
    read<Version[]>(`/runs/${runId}/tickets/${ticketId}/notes/${noteId}/versions`)
      .then(data => { setVersions(data); setMessage(""); })
      .catch(() => setMessage("โหลดประวัติไม่สำเร็จหรือเซสชันหมดอายุ"));
  }, [runId, ticketId, noteId]);
  return <main className="run-shell"><div className="run-topline">
    <Link href={`/runs/${runId}/tickets/${ticketId}`}>กลับไป ticket</Link><span>Note history</span></div>
    <h1>ประวัติบันทึก</h1>{message && <p role="status">{message}</p>}
    <ol>{versions.map(item => <li className="run-panel" key={item.version}>
      <h2>Version {item.version} · {item.change_kind}</h2>
      <p>{item.body}</p><p>หลักฐาน: {item.evidence_ids.join(", ") || "ไม่มี"}</p>
      {item.reason && <p>เหตุผล: {item.reason}</p>}
      <p className="run-muted">{new Date(item.created_at).toLocaleString("th-TH")}</p>
    </li>)}</ol>
  </main>;
}
