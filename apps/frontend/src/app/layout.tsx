import type { Metadata } from "next";
import "./globals.css";
import "./original-fonts.css";

export const metadata: Metadata = {
  title: "Watchback",
  description: "위험 변화 기반 Dependabot Alert 재검토",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
