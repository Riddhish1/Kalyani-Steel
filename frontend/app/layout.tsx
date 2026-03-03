import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KSL Scrap Mix Optimizer",
  description: "EAF Scrap Mix Optimization System"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
