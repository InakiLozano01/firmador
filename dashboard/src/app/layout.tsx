import type { Metadata } from "next";
import { Outfit, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Observability Dashboard — Signing & Validation Monitor",
  description: "Real-time observability dashboard for document signing and validation operations. Track operations, stages, entries, errors and performance metrics.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function(){
                try {
                  var t = localStorage.getItem('theme');
                  var d = t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme:dark)').matches);
                  document.documentElement.classList.toggle('dark', d);
                  document.documentElement.classList.toggle('light', !d);
                  document.documentElement.style.colorScheme = d ? 'dark' : 'light';
                } catch(e){}
              })();
            `,
          }}
        />
      </head>
      <body className={`${outfit.variable} ${jetbrainsMono.variable} font-sans`}>
        {children}
      </body>
    </html>
  );
}
