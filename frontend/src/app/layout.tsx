import type { Metadata } from "next";
import { Geist_Mono, Instrument_Sans } from "next/font/google";

import { AppShell } from "@/components";

import "./globals.css";

const instrumentSans = Instrument_Sans({
  subsets: ["latin"],
  variable: "--font-instrument-sans",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PaperTrail",
  description:
    "A local research workspace: discover, understand, compare, and build on papers.",
};

/* Appearance settings are read before first paint so the app never flashes
   the wrong theme. They live in localStorage because PaperTrail runs on one
   machine for one person; there is no profile to sync them to. */
const APPEARANCE_BOOTSTRAP = `(function(){try{
var d=document.documentElement,s=window.localStorage;
var t=s.getItem('pt-theme'); if(t==='light'||t==='dark') d.setAttribute('data-theme',t);
var n=s.getItem('pt-nav'); if(n==='top') d.setAttribute('data-nav','top');
var y=s.getItem('pt-density'); if(y==='compact') d.setAttribute('data-density','compact');
var r=s.getItem('pt-reading'); if(r) d.style.setProperty('--reading-size', r+'px');
}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${instrumentSans.variable} ${geistMono.variable}`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: APPEARANCE_BOOTSTRAP }} />
      </head>
      <body className="antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
