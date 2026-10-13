"use client";
import Link from "next/link";
import { createContext, useContext, useEffect, useState, useCallback, useRef } from "react";
import { ApiError, mutate, read, type SessionData } from "../lib/api";

type State = { session: SessionData | null; loading: boolean; error: string; refresh: () => Promise<void> };
const Context = createContext<State | null>(null);
export function useSession() {
  const state = useContext(Context);
  if (!state) throw new Error("Session provider missing");
  return state;
}
export default function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const refresh = useCallback(() => {
    const current = ++generation.current;
    return read<SessionData>("/auth/session")
    .then(session => { if (current === generation.current) { setSession(session); setError(""); } })
    .catch(error => {
      if (current !== generation.current) return;
      setSession(null);
      setError(error instanceof ApiError && error.status === 401 ? "" : "ตรวจสถานะบัญชีไม่ได้ กรุณาลองอีกครั้ง");
    }).finally(() => { if (current === generation.current) setLoading(false); });
  }, []);
  useEffect(() => {
    void refresh();
    const focus = () => { void refresh(); };
    window.addEventListener("focus", focus);
    const timer = window.setInterval(focus, 60000);
    return () => { window.removeEventListener("focus", focus); window.clearInterval(timer); };
  }, [refresh]);
  async function logout() {
    try { await mutate<void>("/auth/logout", {}); ++generation.current; setSession(null); setError(""); setLoading(false); }
    catch { setError("ออกจากระบบไม่สำเร็จ กรุณาลองอีกครั้ง"); }
  }
  return <Context.Provider value={{ session, loading, error, refresh }}>
    <nav className="account-nav" aria-label="บัญชี">
      <Link href="/">Sentinel</Link><Link href="/demo">ดูตัวอย่าง</Link>
      {loading ? <span role="status">กำลังตรวจบัญชี…</span> : session ? <>
        <Link href="/account">{session.user.display_name}</Link>
        <button onClick={() => void logout()}>ออกจากระบบ</button>
      </> : <><Link href="/login">เข้าสู่ระบบ</Link><Link href="/register">สมัครสมาชิก</Link></>}
    </nav>
    {error && <p role="alert" className="account-message">{error} <button onClick={() => void refresh()}>ลองใหม่</button></p>}
    {children}
  </Context.Provider>;
}
