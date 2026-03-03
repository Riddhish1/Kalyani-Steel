import type { Metadata } from "next";
import Image from "next/image";
import "./globals.css";
import logo from "./logo.png";

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
      <head>
        <link rel="icon" href={(logo as any).src || logo} />
      </head>
      <body>
        <header className="p-4 flex items-center">
          <Image src={logo} alt="Kalyani Steel" width={48} height={48} />
          <h1 className="ml-3 text-xl font-semibold">KSL Scrap Mix Optimizer</h1>
        </header>
        {children}
      </body>
    </html>
  );
}
