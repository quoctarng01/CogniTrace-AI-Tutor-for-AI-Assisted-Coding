// File: frontend/app/examples/[id]/loading.tsx
export default function Loading() {
  return (
    <div style={{ minHeight: '100vh', background: '#0d1117', padding: '32px 24px' }}>
      {/* Top bar skeleton */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          maxWidth: '760px',
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

      {/* Content skeleton */}
      <div style={{ maxWidth: '760px', margin: '0 auto' }}>
        <div
          style={{
            height: '40px',
            background: '#21262d',
            borderRadius: '8px',
            marginBottom: '24px',
            maxWidth: '500px',
          }}
        />
        <div
          style={{
            height: '200px',
            background: '#161b22',
            border: '1px solid #21262d',
            borderRadius: '10px',
            marginBottom: '24px',
          }}
        />
        <div
          style={{
            height: '100px',
            background: '#161b22',
            border: '1px solid #21262d',
            borderRadius: '8px',
          }}
        />
      </div>
    </div>
  );
}
