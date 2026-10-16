"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";
import { ApiError, mutate, read, type SessionData } from "../lib/api";

type State = {
  session: SessionData | null;
  loading: boolean;
  error: string;
  refresh: () => Promise<void>;
  preview: boolean;
};
const Context = createContext<State | null>(null);
export function useSession() {
  const state = useContext(Context);
  if (!state) throw new Error("Session provider missing");
  return state;
}
export default function SessionProvider({
  children,
  preview = false,
}: {
  children: React.ReactNode;
  preview?: boolean;
}) {
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);
  const [session, setSession] = useState<SessionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const refresh = useCallback(() => {
    const current = ++generation.current;
    return read<SessionData>("/auth/session")
      .then((session) => {
        if (current === generation.current) {
          setSession(session);
          setError("");
        }
      })
      .catch((error) => {
        if (current !== generation.current) return;
        setSession(null);
        setError(
          error instanceof ApiError && error.status === 401
            ? ""
            : "ตรวจสถานะบัญชีไม่ได้ กรุณาลองอีกครั้ง",
        );
      })
      .finally(() => {
        if (current === generation.current) setLoading(false);
      });
  }, []);
  useEffect(() => {
    void refresh();
    const focus = () => {
      void refresh();
    };
    window.addEventListener("focus", focus);
    const timer = window.setInterval(focus, 60000);
    return () => {
      window.removeEventListener("focus", focus);
      window.clearInterval(timer);
    };
  }, [refresh]);
  async function logout() {
    try {
      await mutate<void>("/auth/logout", {});
      ++generation.current;
      setSession(null);
      setError("");
      setLoading(false);
      setNavOpen(false);
    } catch {
      setError("ออกจากระบบไม่สำเร็จ กรุณาลองอีกครั้ง");
    }
  }
  return (
    <Context.Provider value={{ session, loading, error, refresh, preview }}>
      {preview && (
        <p role="status" className="account-message">
          Free preview: ทดสอบสมัครสมาชิก/เข้าสู่ระบบและดูตัวอย่างได้ ·
          ยังเริ่มรอบฝึกไม่ได้ เพราะไม่มี background runner · AI เป็น mock ·
          ฐานข้อมูลชั่วคราว ห้ามใส่ข้อมูลจริง
        </p>
      )}
      <a href="#main-content" className="skip-link">
        ข้ามไปเนื้อหา
      </a>
      <nav className="account-nav" aria-label="บัญชี" data-open={navOpen}>
        <Link
          className="nav-brand"
          href="/"
          onClick={() => setNavOpen(false)}
          aria-label="Sentinel"
        >
          <span className="brand-mark" aria-hidden="true">
            S
          </span>
          <span>
            Sentinel<small>SOC LEARNING LAB</small>
          </span>
        </Link>
        <button
          className="nav-toggle"
          type="button"
          aria-expanded={navOpen}
          aria-controls="primary-links account-links"
          onClick={() => setNavOpen((value) => !value)}
        >
          <span aria-hidden="true">{navOpen ? "×" : "☰"}</span>
          {navOpen ? "ปิดเมนู" : "เมนู"}
        </button>
        <div className="nav-links" id="primary-links">
          <Link
            href="/demo"
            onClick={() => setNavOpen(false)}
            aria-current={pathname === "/demo" ? "page" : undefined}
          >
            ดูตัวอย่าง
          </Link>
          <Link
            href="/scenarios"
            onClick={() => setNavOpen(false)}
            aria-current={pathname === "/scenarios" ? "page" : undefined}
          >
            สถานการณ์ฝึก
          </Link>
          {session && (
            <Link
              href="/runs"
              onClick={() => setNavOpen(false)}
              aria-current={pathname.startsWith("/runs") ? "page" : undefined}
            >
              รอบฝึกของฉัน
            </Link>
          )}
        </div>
        <div className="nav-account" id="account-links">
          {loading ? (
            <span role="status">กำลังตรวจบัญชี…</span>
          ) : session ? (
            <>
              <Link
                href="/account"
                onClick={() => setNavOpen(false)}
                aria-current={pathname === "/account" ? "page" : undefined}
              >
                {session.user.display_name}
              </Link>
              <button onClick={() => void logout()}>ออกจากระบบ</button>
            </>
          ) : (
            <>
              <Link
                href="/login"
                onClick={() => setNavOpen(false)}
                aria-current={pathname === "/login" ? "page" : undefined}
              >
                เข้าสู่ระบบ
              </Link>
              <Link
                className="nav-cta"
                href="/register"
                onClick={() => setNavOpen(false)}
              >
                สมัครสมาชิก <span aria-hidden="true">↗</span>
              </Link>
            </>
          )}
        </div>
      </nav>
      {error && (
        <p role="alert" className="account-message">
          {error} <button onClick={() => void refresh()}>ลองใหม่</button>
        </p>
      )}
      <div id="main-content" tabIndex={-1}>
        {children}
      </div>
    </Context.Provider>
  );
}
