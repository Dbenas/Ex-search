import type { Metadata } from "next";
import { IBM_Plex_Mono, Schibsted_Grotesk, Source_Serif_4 } from "next/font/google";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const schibsted = Schibsted_Grotesk({
  subsets: ["latin"],
  variable: "--font-schibsted",
});

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  variable: "--font-source-serif",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "Curadoria Executiva",
  description: "Shortlist de executivos C-Level com parecer fundamentado em evidências.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="pt-BR"
      className={`${schibsted.variable} ${sourceSerif.variable} ${plexMono.variable}`}
    >
      <body className="min-h-screen">
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
