import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sentinel | SOC Learning Lab",
  description: "ห้องเรียนสืบสวนเหตุการณ์ SOC จากข้อมูลจำลอง — อยู่ระหว่างพัฒนา",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="th"><body>{children}</body></html>;
}
