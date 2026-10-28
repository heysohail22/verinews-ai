import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VeriNews | AI & Technology News",
  description: "Discover recent AI reporting and create source-grounded drafts for X and LinkedIn.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
