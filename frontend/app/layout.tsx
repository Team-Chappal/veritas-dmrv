import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VERITAS dMRV",
  description:
    "AI-powered impact & sustainability media intelligence platform — visual ground-truth and cryptographic media provenance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-canvas text-slate-200 antialiased">{children}</body>
    </html>
  );
}
