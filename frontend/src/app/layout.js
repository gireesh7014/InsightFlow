/**
 * ROOT LAYOUT
 * ===========
 * This is Next.js's root layout — wraps EVERY page in the app.
 * 
 * NEXT.JS APP ROUTER:
 *   In the App Router, layout.js wraps page.js automatically.
 *   Think of it as the HTML skeleton that never changes:
 *   <html> + <body> + fonts + metadata are set here once.
 *   
 *   page.js provides the page content that goes inside this layout.
 * 
 * GOOGLE FONTS:
 *   Next.js has built-in font optimization. Instead of adding a <link>
 *   tag (which blocks rendering), Next.js downloads the font at build
 *   time and serves it from your own domain. Zero layout shift.
 */
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// SEO Metadata — this generates the <title> and <meta> tags
export const metadata = {
  title: "InsightFlow — Decision Intelligence System",
  description:
    "Upload CSV datasets and get ranked, explainable insights with statistical analysis, anomaly detection, and auto-generated visualizations.",
  keywords: ["data analysis", "insights", "machine learning", "CSV", "decision intelligence"],
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[var(--background)] text-[var(--foreground)]">
        {children}
      </body>
    </html>
  );
}
