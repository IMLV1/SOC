import { redirect } from "next/navigation";

export const metadata = { title: "เส้นทางเรียนรู้ — Sentinel" };

export default async function LearningPreviewPage({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const { view } = await searchParams;
  redirect(view === "practice" ? "/practice" : "/learning");
}
