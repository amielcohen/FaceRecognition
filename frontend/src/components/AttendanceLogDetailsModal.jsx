import styles from './AttendanceLogDetailsModal.module.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function AttendanceLogDetailsModal({ log, onClose }) {
  const isUnknown = (log.matched_name || '').toLowerCase() === 'unknown'

  function formatDate(value) {
    if (!value) return '-'

    const date = new Date(value)

    if (Number.isNaN(date.getTime())) {
      return value
    }

    return date.toLocaleString()
  }

  function formatDistance(value) {
    if (value === null || value === undefined) return '-'
    return Number(value).toFixed(4)
  }

  const cropUrl = log.crop_path
    ? `${API_BASE_URL}/attendance-crop?path=${encodeURIComponent(log.crop_path)}`
    : null

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <div>
            <h2>Attendance Log Details</h2>
            <p>Full information about the selected recognition event.</p>
          </div>

          <button className={styles.closeButton} onClick={onClose}>
            ×
          </button>
        </div>

        <div className={styles.content}>
          <div className={styles.imageSection}>
            {cropUrl ? (
              <img
                src={cropUrl}
                alt="Saved face crop"
                className={styles.cropImage}
              />
            ) : (
              <div className={styles.noImage}>No crop image saved</div>
            )}
          </div>

          <div className={styles.detailsSection}>
            <div className={styles.row}>
              <span>ID</span>
              <strong>{log.id}</strong>
            </div>

            <div className={styles.row}>
              <span>Name</span>
              <strong>{log.matched_name || '-'}</strong>
            </div>

            <div className={styles.row}>
              <span>Status</span>
              <strong
                className={
                  isUnknown ? styles.unknownText : styles.identifiedText
                }
              >
                {isUnknown ? 'Unknown' : 'Identified'}
              </strong>
            </div>

            <div className={styles.row}>
              <span>Distance</span>
              <strong>{formatDistance(log.distance)}</strong>
            </div>

            <div className={styles.row}>
              <span>Track ID</span>
              <strong>{log.track_id ?? '-'}</strong>
            </div>

            <div className={styles.row}>
              <span>Entry Time</span>
              <strong>{formatDate(log.entry_time)}</strong>
            </div>

            <div className={styles.row}>
              <span>Crop Path</span>
              <strong className={styles.pathText}>{log.crop_path || '-'}</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}