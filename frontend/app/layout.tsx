import type { Metadata } from "next";
import AppShell from "@/components/rq/AppShell";
import { SessionProvider } from "@/lib/api/session";
import { RqProvider } from "@/lib/rq/store";
import "./globals.css";

export const metadata: Metadata = {
  title: "Revisión de requerimientos · orquestador multiagente",
  description:
    "Prototipo: un orquestador y agentes especialistas revisan código, pruebas, Kiuwan, SQL, UI/UX y generan el VTR de cada requerimiento.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="min-h-screen bg-paper font-sans text-ink-900 antialiased">
        <SessionProvider>
          <RqProvider>
            <AppShell>{children}</AppShell>
          </RqProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
