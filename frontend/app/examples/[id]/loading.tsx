// File: frontend/app/examples/[id]/loading.tsx
export default function Loading() {
  return (
    <div style={{ padding: "32px 24px", maxWidth: "760px", margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "32px" }}>
        <div style={{ width: "80px", height: "20px", background: "#f3f4f6", borderRadius: "4px" }} />
        <div style={{ width: "100px", height: "24px", background: "#f3f4f6", borderRadius: "4px" }} />
        <div style={{ width: "80px" }} />
      </div>
      <div style={{ height: "40px", background: "#f3f4f6", borderRadius: "8px", marginBottom: "24px", maxWidth: "500px" }} />
      <div style={{ height: "200px", background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: "10px", marginBottom: "24px" }} />
      <div style={{ height: "100px", background: "#f9fafb", border: "1px solid #e5e7eb", borderRadius: "8px" }} />
    </div>
  );
}
