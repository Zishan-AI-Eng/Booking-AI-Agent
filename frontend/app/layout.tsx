import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "US-Duct | Project Desk",
  description: "Industrial ventilation consultation assistant",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
