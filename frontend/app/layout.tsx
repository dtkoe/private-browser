import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Genesis Browser",
  description: "Anti-detect browser manager",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
