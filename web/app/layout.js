import "./globals.css";

// Todas las paginas leen la base en cada visita; nunca se sirven datos guardados de antes
export const dynamic = "force-dynamic";
export const fetchCache = "force-no-store";

export const metadata = {
  title: "Normas Legales del Perú",
  description: "Buscador de normas legales publicadas en El Peruano, clasificadas por sector y rubro.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
