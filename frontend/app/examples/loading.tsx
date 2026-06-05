// File: frontend/app/examples/loading.tsx
export default function Loading() {
  return (
    <div style={{ minHeight: '100vh', background: '#0d1117', padding: '32px 24px' }}>
      {/* Top bar skeleton */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          maxWidth: '960px',
          margin: '0 auto 32px',
          padding: '0 0 16px',
          borderBottom: '1px solid #21262d',
        }}
      >
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <div style={{ width: '20px', height: '20px', background: '#30363d', borderRadius: '4px' }} />
          <div style={{ width: '80px', height: '16px', background: '#30363d', borderRadius: '4px' }} />
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <div style={{ width: '80px', height: '32px', background: '#21262d', borderRadius: '6px' }} />
          <div style={{ width: '80px', height: '32px', background: '#21262d', borderRadius: '6px' }} />
        </div>
      </div>

      {/* Tabs skeleton */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', maxWidth: '960px', margin: '0 auto 24px' }}>
        {[80, 100, 90, 70, 85, 95].map((w, i) => (
          <div
            key={i}
            style={{ width: w, height: '32px', background: '#21262d', borderRadius: '16px' }}
          />
        ))}
      </div>

      {/* Grid skeleton */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: '16px',
          maxWidth: '960px',
          margin: '0 auto',
        }}
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            style={{
              height: '180px',
              background: '#161b22',
              border: '1px solid #21262d',
              borderRadius: '12px',
            }}
          />
        ))}
      </div>
    </div>
  );
}
