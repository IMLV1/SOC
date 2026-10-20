import type { Metadata } from "next";
import "./globals.css";
import SessionProvider from "./session-provider";

export const metadata: Metadata = {
  title: "Sentinel — SOC Learning Lab",
  description:
    "ห้องทดลอง SOC สำหรับฝึกอ่านหลักฐาน เชื่อมโยงเหตุการณ์ และอธิบายข้อสรุปจากข้อมูลจำลอง",
};

// The root layout owns the shared session context for every App Router page.
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th">
      <body>
        <SessionProvider preview={process.env.SOC_PREVIEW_MODE === "auth_only"}>
          {children}
        </SessionProvider>
      </body>
    </html>
  );
}
