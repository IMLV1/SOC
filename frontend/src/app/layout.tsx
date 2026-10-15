import type { Metadata } from "next";
import "./globals.css";
import SessionProvider from "./session-provider";

export const metadata: Metadata = {
  title: "Sentinel | SOC Learning Lab",
  description: "ห้องเรียนสืบสวนเหตุการณ์ SOC จากข้อมูลจำลอง — อยู่ระหว่างพัฒนา",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="th"><body><SessionProvider preview={process.env.SOC_PREVIEW_MODE === "auth_only"}>{children}</SessionProvider></body></html>;
}
