import { useEffect, useState } from 'react'
import styles from './DashboardPage.module.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default function DashboardPage() {
  const [status, setStatus] = useState('unknown')
  const [stats, setStats] = useState({
    employees_count: 0,
    logs_today: 0,
    unknown_today: 0,
    last_recognition: null,
  })
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState('')
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  async function loadDashboard(showLoader = false) {
  try {
    if (showLoader) {
      setLoading(true)
    }

    setError('')

    const response = await fetch(`${API_BASE_URL}/dashboard`)

    if (!response.ok) throw new Error('Failed to load dashboard')

    const data = await response.json()

    setStatus(data.status || 'unknown')
    setStats(data.stats || stats)
  } catch (err) {
    console.error(err)
    setError('Failed to load dashboard data')
  } finally {
    if (showLoader) {
      setLoading(false)
    }
  }
}

  useEffect(() => {
    loadDashboard(true)
  }, [])

  useEffect(() => {
  if (status !== 'starting') {
    return
  }

  const intervalId = setInterval(() => {
    loadDashboard(false)
  }, 2000)

  return () => clearInterval(intervalId)
}, [status])

  async function handleSystemAction(action) {
    try {
      setActionLoading(action)
      setError('')
      setSuccessMessage('')
      const response = await fetch(`${API_BASE_URL}/system/${action}`, {
        method: 'POST',
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || `Failed to ${action} system`)
      setSuccessMessage(data.message || `System ${action} completed`)
      await loadDashboard()
    } catch (err) {
      setError(err.message)
    } finally {
      setActionLoading('')
      // העלמת הודעת ההצלחה אחרי 4 שניות
      setTimeout(() => setSuccessMessage(''), 4000)
    }
  }

  function formatDate(value) {
    if (!value) return 'No events yet'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
  }

  return (
    <div className={styles.page}>
      <div className={styles.topSection}>
        <div>
          <h1>System Dashboard</h1>
          <p>Real-time overview and core engine controls.</p>
        </div>
        <button className={styles.refreshButton} onClick={loadDashboard}>
          ↺ Refresh Data
        </button>
      </div>

      {error && <div className={styles.errorCard}>⚠️ {error}</div>}
      {successMessage && <div className={styles.successCard}>✓ {successMessage}</div>}

      {loading ? (
        <div className={styles.loadingOverlay}>Initializing Dashboard...</div>
      ) : (
        <div className={styles.dashboardGrid}>
          
          {/* כרטיס סטטוס מערכת */}
          <div className={`${styles.card} ${styles.statusMainCard}`}>
            <div className={styles.statusInfo}>
              <span className={styles.label}>Engine Status</span>
              <h2 className={status === 'running' ? styles.statusRunning :
                 status === 'starting' ? styles.statusStarting : styles.statusStopped}>
                {status.toUpperCase()}
              </h2>
            </div>
            <div className={status === 'running' ? styles.pulseContainer : status === 'starting' ? styles.startingContainer : styles.staticContainer}>
              <div className={status === 'running' ? styles.runningDot :  status === 'starting' ? styles.startingDot : styles.stoppedDot} />
            </div>
          </div>

          {/* כפתורי פעולה מהירים */}
          <div className={`${styles.card} ${styles.actionsCard}`}>
            <span className={styles.label}>Quick Controls</span>
            <div className={styles.actionButtons}>
              <button
                className={styles.startButton}
                onClick={() => handleSystemAction('start')}
                disabled={!!actionLoading || status === 'running'}
              >
                {actionLoading === 'start' ? '...' : '▶ Start'}
              </button>

              <button
                className={styles.restartButton}
                onClick={() => handleSystemAction('restart')}
                disabled={!!actionLoading}
              >
                {actionLoading === 'restart' ? '...' : '↻ Restart'}
              </button>

              <button
                className={styles.stopButton}
                onClick={() => handleSystemAction('stop')}
                disabled={!!actionLoading || status === 'stopped'}
              >
                {actionLoading === 'stop' ? '...' : '■ Stop'}
              </button>
            </div>
          </div>

          {/* גריד סטטיסטיקות */}
          <div className={styles.statsContainer}>
            <div className={styles.statBox}>
              <span className={styles.statLabel}>Total Employees</span>
              <strong className={styles.statValue}>{stats.employees_count}</strong>
            </div>

            <div className={styles.statBox}>
              <span className={styles.statLabel}>Recognitions (Today)</span>
              <strong className={styles.statValue}>{stats.logs_today}</strong>
            </div>

            <div className={`${styles.statBox} ${stats.unknown_today > 0 ? styles.alertStat : ''}`}>
              <span className={styles.statLabel}>Unknown Faces</span>
              <strong className={styles.statValue}>{stats.unknown_today}</strong>
            </div>

            <div className={`${styles.statBox} ${styles.fullWidthStat}`}>
              <span className={styles.statLabel}>Last Recognition Event</span>
              <strong className={styles.dateValue}>{formatDate(stats.last_recognition)}</strong>
            </div>
          </div>

        </div>
      )}
    </div>
  )
}