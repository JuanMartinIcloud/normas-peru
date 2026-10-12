import "./globals.css";

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
