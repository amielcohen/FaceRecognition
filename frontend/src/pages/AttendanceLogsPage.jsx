import { useEffect, useMemo, useState } from 'react'
import { getAttendanceLogs } from '../api/attendanceApi'
import AttendanceLogDetailsModal from '../components/AttendanceLogDetailsModal'
import styles from './AttendanceLogsPage.module.css'

export default function AttendanceLogsPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedLog, setSelectedLog] = useState(null)

  // Filters State
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

  async function loadLogs() {
    try {
      setLoading(true)
      setError('')
      const data = await getAttendanceLogs({
        limit: 300,
        offset: 0,
      })
      setLogs(data.items || [])
    } catch (err) {
      console.error(err)
      setError('Failed to load attendance logs')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLogs()
  }, [])

  const filteredLogs = useMemo(() => {
    return logs.filter((log) => {
      const name = (log.matched_name || '').toLowerCase()
      const isUnknown = name === 'unknown'

      // Search filter
      if (search.trim() && !name.includes(search.toLowerCase())) {
        return false
      }

      // Status filter (הלוגיקה נשארת זהה, הממשק השתנה)
      if (statusFilter === 'identified' && isUnknown) return false
      if (statusFilter === 'unknown' && !isUnknown) return false

      // Date filter
      if (startDate || endDate) {
        const logDate = new Date(log.entry_time)
        if (startDate) {
          const start = new Date(startDate)
          start.setHours(0, 0, 0, 0)
          if (logDate < start) return false
        }
        if (endDate) {
          const end = new Date(endDate)
          end.setHours(23, 59, 59, 999)
          if (logDate > end) return false
        }
      }
      return true
    })
  }, [logs, search, statusFilter, startDate, endDate])

  function formatDate(value) {
    if (!value) return '-'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
  }

  function formatDistance(value) {
    return (value === null || value === undefined) ? '-' : Number(value).toFixed(4)
  }

  return (
    <div className={styles.page}>
      <div className={styles.topSection}>
        <div>
          <h1>Attendance Logs</h1>
          <p>View recognition history, unknown detections, and saved crops.</p>
        </div>
        <button className={styles.refreshButton} onClick={loadLogs}>
          Refresh List
        </button>
      </div>

      <div className={styles.filtersContainer}>
        <div className={styles.searchWrapper}>
          <input
            type="text"
            placeholder="Search by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={styles.searchInput}
          />
        </div>

        {/* בחירת סטטוס - כפתורים לחיצים במקום Select */}
        <div className={styles.statusToggleGroup}>
          {[
            { id: 'all', label: 'All' },
            { id: 'identified', label: 'Identified' },
            { id: 'unknown', label: 'Unknown' }
          ].map((option) => (
            <button
              key={option.id}
              className={`${styles.toggleButton} ${statusFilter === option.id ? styles.active : ''}`}
              onClick={() => setStatusFilter(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className={styles.dateFilters}>
          <div className={styles.dateGroup}>
            <label>From</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className={styles.dateInput}
            />
          </div>
          <div className={styles.dateGroup}>
            <label>To</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className={styles.dateInput}
            />
          </div>
        </div>
      </div>

      {loading && <div className={styles.message}>Loading attendance logs...</div>}
      {error && <div className={styles.errorCard}>{error}</div>}

      {!loading && !error && filteredLogs.length === 0 && (
        <div className={styles.message}>No logs found matching your filters.</div>
      )}

      {!loading && !error && filteredLogs.length > 0 && (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Status</th>
                <th>Distance</th>
                <th>Track ID</th>
                <th>Entry Time</th>
                <th>Crop</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => {
                const isUnknown = (log.matched_name || '').toLowerCase() === 'unknown'
                return (
                  <tr
                    key={log.id}
                    className={styles.clickableRow}
                    onClick={() => setSelectedLog(log)}
                  >
                    <td>{log.id}</td>
                    <td className={styles.nameCell}>{log.matched_name || '-'}</td>
                    <td>
                      <span className={isUnknown ? styles.unknownBadge : styles.identifiedBadge}>
                        {isUnknown ? 'Unknown' : 'Identified'}
                      </span>
                    </td>
                    <td>{formatDistance(log.distance)}</td>
                    <td>{log.track_id ?? '-'}</td>
                    <td>{formatDate(log.entry_time)}</td>
                    <td>
                      <span className={log.crop_path ? styles.linkText : ''}>
                        {log.crop_path ? 'View Crop' : '-'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {selectedLog && (
        <AttendanceLogDetailsModal
          log={selectedLog}
          onClose={() => setSelectedLog(null)}
        />
      )}
    </div>
  )
}