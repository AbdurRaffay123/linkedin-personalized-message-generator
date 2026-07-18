import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Sales Assistant",
  description: "Decision-grade prospect research briefs.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-3xl px-5 py-6">
          <header className="mb-6 flex items-center justify-between border-b border-neutral-200 pb-4 dark:border-neutral-800">
            <Link href="/" className="text-lg font-semibold">
              AI Sales Assistant
            </Link>
            <span className="text-xs text-neutral-500">
              decision-grade prospect briefs
            </span>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
