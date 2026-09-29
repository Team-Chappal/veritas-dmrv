import type { Metadata } from "next";
import "./globals.css";
import { ThemeProvider } from "@/components/ThemeContext";

export const metadata: Metadata = {
  title: "VERITAS dMRV · Planetary Ground Truth & Forensic Media Intelligence",
  description:
    "Open digital Measurement, Reporting, and Verification (dMRV) platform. Astronomical solar physics, SIFT homography computer vision, Chave 2014 allometry, and cryptographic C2PA provenance.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="scroll-smooth">
      <body className="bg-canvas text-slate-900 dark:text-slate-100 antialiased min-h-screen">
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
