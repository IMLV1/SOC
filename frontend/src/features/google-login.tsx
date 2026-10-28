"use client";
import { Google } from "@thesvg/react";
import { useEffect, useState } from "react";
import { ApiError, mutate, read } from "../lib/api";
import type {
  GoogleStatusData as GoogleStatus,
  GoogleStartData as GoogleStart,
} from "../lib/api-types";

export default function GoogleLogin({
  account = false,
}: {
  account?: boolean;
}) {
  const [status, setStatus] = useState<GoogleStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [password, setPassword] = useState("");
  useEffect(() => {
    let active = true;
    read<GoogleStatus>("/auth/google/status")
      .then((value) => {
        if (!active) return;
        setStatus(value);
        const result = new URLSearchParams(window.location.search).get(
          "google",
        );
        if (result === "failed")
          setMessage("เข้าสู่ระบบ Google ไม่สำเร็จหรือยกเลิก กรุณาลองใหม่");
        if (result === "link_required")
          setMessage(
            "มีบัญชี SOC อีเมลนี้แล้ว กรุณาเข้าสู่ระบบด้วยรหัสผ่าน แล้วเชื่อม Google ที่หน้าบัญชี",
          );
      })
      .catch((error) => {
        if (!active) return;
        // Older preview APIs do not expose Google routes yet.
        if (error instanceof ApiError && error.status === 404) {
          setStatus({ available: false, linked: false });
          return;
        }
        setMessage("ตรวจสถานะ Google ไม่สำเร็จ กรุณาโหลดหน้าใหม่");
      });
    return () => {
      active = false;
    };
  }, []);
  async function start(event?: React.FormEvent) {
    event?.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const result = await mutate<GoogleStart>(
        "/auth/google/start",
        account ? { purpose: "link", password } : { purpose: "login" },
      );
      setPassword("");
      const destination = new URL(result.authorization_url);
      const supabaseOrigin = status?.provider_origin;
      const supabase = !!supabaseOrigin &&
        /^https:\/\/[a-z0-9]{20}\.supabase\.co$/.test(supabaseOrigin) &&
        destination.origin === supabaseOrigin &&
        destination.pathname === "/auth/v1/authorize" &&
        destination.searchParams.get("provider") === "google";
      if (
        !supabase && (destination.origin !== "https://accounts.google.com" ||
        destination.pathname !== "/o/oauth2/v2/auth")
      )
        throw new Error("Invalid authorization URL");
      window.location.assign(destination.href);
    } catch (error) {
      setMessage(
        error instanceof ApiError && error.status === 401
          ? "กรุณาตรวจรหัสผ่านหรือเข้าสู่ระบบใหม่"
          : error instanceof ApiError && error.status === 429
            ? "คำขอถี่เกินไป กรุณารอหนึ่งนาที"
            : "เริ่มเชื่อมต่อ Google ไม่สำเร็จ กรุณาลองใหม่",
      );
      setBusy(false);
    }
  }
  return (
    <section className="google-login" aria-label="Google login">
      {!status && !message && <p role="status">กำลังตรวจ Google login…</p>}
      {status && !status.available && (
        <p>Google login ยังไม่เปิดใช้งานใน environment นี้</p>
      )}
      {status?.linked ? (
        <p>เชื่อมบัญชี Google แล้ว ใช้ Google เข้าบัญชีเดิมได้</p>
      ) : account && status?.link_available === false ? (
        <p>บัญชีนี้ยังไม่ได้เชื่อม Google</p>
      ) : (
        status?.available &&
        (account ? (
          <form onSubmit={start}>
            <p>
              เชื่อม Google อีเมลเดียวกับบัญชีนี้ โดยยืนยันรหัสผ่าน SOC ครั้งแรก
            </p>
            <label>
              ยืนยันรหัสผ่าน SOC
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={12}
                maxLength={128}
              />
            </label>
            <button disabled={busy} type="submit">
              {busy ? "กำลังเชื่อมต่อ…" : "เชื่อมบัญชี Google"}
            </button>
          </form>
        ) : (
          <>
            <button disabled={busy} type="button" onClick={() => start()}>
              <Google
                className="google-logo"
                width={24}
                height={24}
                aria-hidden="true"
                focusable="false"
              />
              {busy ? "กำลังไป Google…" : "เข้าสู่ระบบด้วย Google"}
            </button>
            <p>
              ใช้บัญชี Google เพื่อเข้าสู่ระบบหรือเริ่มบัญชีผู้เรียนใหม่
            </p>
          </>
        ))
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
