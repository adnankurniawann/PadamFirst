import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PadamFirst",
  description: "Peta prioritas pemadaman titik api karhutla di Indonesia",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="id" className="h-full">
      <body className="h-full">{children}</body>
    </html>
  );
}
