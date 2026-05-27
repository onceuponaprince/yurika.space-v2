import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Press_Start_2P } from "next/font/google";

import { Providers } from "@/components/Providers";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

const pressStart = Press_Start_2P({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "yurika.space — Liquid Domains. Accelerated Founders.",
    template: "%s | yurika.space",
  },
  description:
    "Fractionalize your domain ownership, raise instant capital, and accelerate your vision. The default launchpad for domain-first startups.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${inter.variable} ${jetbrains.variable} ${pressStart.variable}`}
    >
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
