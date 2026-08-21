import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Demo multiagente · trazas de comunicación entre agentes",
  description:
    "Demo educativa: visualización en tiempo real de cómo varios agentes de IA se comunican para analizar activos. No constituye asesoramiento financiero.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
