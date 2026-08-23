import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import type { Metadata, Viewport } from "next";
import "./globals.css";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500"],
  style: ["normal", "italic"],
  variable: "--font-ibm-sans",
  display: "swap",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-ibm-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "DeepRead",
    template: "%s · DeepRead",
  },
  description: "A local library for technical books you extract from PDFs or markdown notes.",
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
  width: "device-width",
  initialScale: 1,
};

const themeScript = `try{var t=localStorage.getItem("ie-theme");if(t==="night")document.documentElement.dataset.theme="night"}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className="h-full bg-page text-ink">{children}</body>
    </html>
  );
}
