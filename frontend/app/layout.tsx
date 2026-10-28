import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VeriNews | AI & Technology News",
  description: "Collect the latest AI and technology reporting from RSS feeds and read the original stories.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
