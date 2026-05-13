import type { Metadata } from "next";
import "./globals.css";
import { SupabaseListener } from "./supabase-provider";

export const metadata: Metadata = {
  title: "CodeScope",
  description: "Visualize Python code execution step by step",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="dark">
        <SupabaseListener />
        {children}
      </body>
    </html>
  );
}
