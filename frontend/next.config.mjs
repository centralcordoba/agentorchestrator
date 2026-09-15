// Dos modos de salida:
//  - standalone (por defecto): servidor Node propio (Docker / `npm start`).
//  - export (NEXT_OUTPUT=export): HTML/JS estático en `out/`, que FastAPI sirve directamente.
//    En este modo la API se resuelve contra el mismo origen (no hace falta NEXT_PUBLIC_API_URL).
const isExport = process.env.NEXT_OUTPUT === "export";

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: isExport ? "export" : "standalone",
  // En export cada ruta se genera como carpeta con index.html (agentes/index.html, monitor/index.html…),
  // que es lo que StaticFiles de FastAPI sabe servir al recargar la página directamente en esa URL.
  trailingSlash: isExport,
  reactStrictMode: true,
  images: { unoptimized: true },
  env: {
    // Vacío = mismo origen que la página (ver lib/api.ts).
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? (isExport ? "" : "http://localhost:8000"),
  },
};

export default nextConfig;
