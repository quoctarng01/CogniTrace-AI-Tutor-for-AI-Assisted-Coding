// File: frontend/app/examples/loading.tsx
export default function Loading() {
  return (
    <div style={{ padding: "32px 24px", maxWidth: "960px", margin: "0 auto" }}>
      {/* Header skeleton */}
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "32px" }}>
        <div style={{ width: "80px", height: "20px", background: "#f3f4f6", borderRadius: "4px" }} />
        <div style={{ width: "160px", height: "28px", background: "#f3f4f6", borderRadius: "6px" }} />
        <div style={{ width: "80px" }} />
      </div>

      {/* Tabs skeleton */}
      <div style={{ display: "flex", gap: "8px", marginBottom: "24px" }}>
        {[80, 100, 90, 70, 85, 95].map((w, i) => (
          <div key={i} style={{ width: w, height: "32px", background: "#f3f4f6", borderRadius: "16px" }} />
        ))}
      </div>

      {/* Grid skeleton */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            style={{
              height: "180px",
              background: "#f9fafb",
              border: "1px solid #e5e7eb",
              borderRadius: "12px",
            }}
          />
        ))}
      </div>
    </div>
  );
}
