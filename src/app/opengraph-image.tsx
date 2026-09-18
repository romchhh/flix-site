import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "flixмаркет — підписки, які просто працюють";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: "linear-gradient(145deg, #EEF1FA 0%, #DCE3F5 45%, #C9D4F0 100%)",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 999,
              background: "linear-gradient(135deg, #2B5CF6 0%, #8B3DFF 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#fff",
              fontSize: 28,
              fontWeight: 800,
            }}
          >
            ▶
          </div>
          <div style={{ fontSize: 36, fontWeight: 700, color: "#0A0B0E", letterSpacing: "-0.04em" }}>
            flixмаркет
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              fontSize: 72,
              fontWeight: 800,
              lineHeight: 1.02,
              letterSpacing: "-0.04em",
              color: "#0A0B0E",
              textTransform: "uppercase",
              maxWidth: 900,
            }}
          >
            Підписки без зайвих рухів
          </div>
          <div style={{ fontSize: 28, color: "#5A6275", fontWeight: 600, maxWidth: 780 }}>
            Netflix, ChatGPT, Claude та інші. Оплата карткою — доступ у кабінеті.
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 22, color: "#2B5CF6", fontWeight: 700 }}>flix-market.com</div>
          <div style={{ fontSize: 20, color: "#5A6275", fontWeight: 600 }}>Monobank · Telegram · 24/7</div>
        </div>
      </div>
    ),
    { ...size },
  );
}
