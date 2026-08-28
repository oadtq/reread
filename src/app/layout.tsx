import { Inter, JetBrains_Mono, Literata } from "next/font/google";
import type { Metadata, Viewport } from "next";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

// Loaded only to back the optional serif reading preference.
const serif = Literata({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-serif",
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
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
  width: "device-width",
  initialScale: 1,
};

// Applies stored reading preferences before first paint so the reader never
// flashes the default theme or measure.
const bootScript = `(function(){try{
var d=document.documentElement;
var p={};
try{p=JSON.parse(localStorage.getItem("deepread-reader:v1"))||{}}catch(e){}
var t=p.theme;
if(t==="night"||t==="dark")t="dark";else if(t)t="light";
if(!t){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}
d.dataset.theme=t;
if(p.size)d.dataset.size=p.size;
if(p.width)d.dataset.width=p.width;
if(p.face)d.dataset.face=p.face;
}catch(e){}})()`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      data-theme="light"
      className={`${sans.variable} ${mono.variable} ${serif.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: bootScript }} />
      </head>
      <body className="h-full">{children}</body>
    </html>
  );
}
