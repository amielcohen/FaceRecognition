const API_BASE = 'http://127.0.0.1:8000'

export default function LiveMonitorPage() {
  return (
    <div
      style={{
        width: '100%',
        minHeight: '100vh',
        padding: 24,
        boxSizing: 'border-box',
      }}
    >
      <div style={{ marginBottom: 20 }}>
        <h1
          style={{
            color: 'var(--text-primary)',
            margin: 0,
            fontSize: 28,
          }}
        >
          Live Monitor
        </h1>

        <p
          style={{
            color: 'var(--text-secondary)',
            marginTop: 6,
            fontFamily: 'var(--font-mono)',
            fontSize: 13,
          }}
        >
          Real-time face recognition camera stream
        </p>
      </div>

      <div
        style={{
          background: '#111827',
          borderRadius: 18,
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
        }}
      >
        <img
          src={`${API_BASE}/video-feed`}
          alt="Live camera feed"
          style={{
            width: '100%',
            display: 'block',
            objectFit: 'cover',
          }}
        />
      </div>
    </div>
  )
}