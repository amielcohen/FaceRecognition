import { useEffect, useState } from 'react'
import styles from './CameraSettingsPage.module.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

const presetDescriptions = {
  fast: {
    title: 'Fast / Performance',
    description: 'Higher FPS, lower resource usage. Best for older hardware.',
    icon: '⚡'
  },
  balanced: {
    title: 'Balanced',
    description: 'The sweet spot between speed and accuracy. Recommended.',
    icon: '⚖️'
  },
  accurate: {
    title: 'High Accuracy',
    description: 'Stricter recognition quality. Requires more CPU power.',
    icon: '🎯'
  },
}

// חילקתי את השדות לקבוצות כדי שהדף יהיה קריא יותר
const sections = [
  {
    title: 'Detection & Recognition',
    fields: [
      { key: 'min_face_area', label: 'Min Face Area', description: 'Minimum size before processing.', step: 100 },
      { key: 'match_identity_threshold', label: 'Match Threshold', description: 'Strictness of identity matching.', step: 0.01 },
      { key: 'lock_identity_threshold', label: 'Lock Threshold', description: 'Threshold to maintain identity lock.', step: 0.01 },
      { key: 'max_unknown_attempts', label: 'Max Unknown Attempts', description: 'Attempts before marking as unknown.', step: 1 },
    ]
  },
  {
    title: 'Engine Performance',
    fields: [
      { key: 'area_update_ratio', label: 'Update Ratio', description: 'Required growth for crop replacement.', step: 0.1 },
      { key: 'frame_skip_interval', label: 'Frame Skip', description: 'Higher values improve overall FPS.', step: 1 },
    ]
  },
  {
    title: 'Storage & Recording',
    fields: [
      { key: 'retention_hours', label: 'Retention (Hours)', description: 'Data lifespan in the system.', step: 1 },
      { key: 'segment_minutes', label: 'Segment Length', description: 'Recording chunk duration.', step: 1 },
      { key: 'record_res_width', label: 'Record Width', description: 'Video resolution width.', step: 160 },
      { key: 'record_fps', label: 'Recording FPS', description: 'Frame rate for saved videos.', step: 1 },
    ]
  }
]

export default function CameraSettingsPage() {
  const [settings, setSettings] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function loadSettings(showLoader = true) {
    try {
      if (showLoader) setLoading(true)
      setError('')
      const response = await fetch(`${API_BASE_URL}/camera-settings`)
      if (!response.ok) throw new Error('Failed to load settings')
      const data = await response.json()
      setSettings(data)
    } catch (err) {
      setError('Failed to load camera settings')
    } finally {
      if (showLoader) setLoading(false)
    }
  }

  useEffect(() => { loadSettings(true) }, [])

  function updateField(key, value) {
    setSettings((current) => ({
      ...current,
      preset: 'custom',
      [key]: Number(value),
    }))
  }

  async function saveSettings() {
    try {
      setSaving(true)
      setError('')
      setMessage('')
      const response = await fetch(`${API_BASE_URL}/camera-settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Failed to save settings')
      setSettings(data.settings)
      setMessage('Settings updated successfully')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 4000)
    }
  }

  async function applyPreset(presetName) {
    try {
      setSaving(true)
      setError('')
      setMessage('')
      const response = await fetch(`${API_BASE_URL}/camera-settings/preset/${presetName}`, {
        method: 'POST',
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Failed to apply preset')
      setSettings(data.settings)
      setMessage(`Applied ${presetName} preset`)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
      setTimeout(() => setMessage(''), 4000)
    }
  }

  if (loading || !settings) {
    return <div className={styles.loadingState}>Loading configuration...</div>
  }

  return (
    <div className={styles.page}>
      <header className={styles.topSection}>
        <div>
          <h1>Recognition Engine</h1>
          <p>Fine-tune detection thresholds and system performance.</p>
        </div>
        <div className={styles.headerActions}>
          <button className={styles.resetButton} onClick={() => applyPreset('balanced')} disabled={saving}>
            Reset Defaults
          </button>
          <button className={styles.saveButton} onClick={saveSettings} disabled={saving}>
            {saving ? 'Saving...' : 'Save Configuration'}
          </button>
        </div>
      </header>

      {error && <div className={styles.errorBanner}>⚠️ {error}</div>}
      {message && <div className={styles.successBanner}>✓ {message}</div>}

      <section className={styles.presetGrid}>
        {Object.entries(presetDescriptions).map(([key, preset]) => (
          <div 
            key={key} 
            className={`${styles.presetCard} ${settings.preset === key ? styles.activePreset : ''}`}
            onClick={() => !saving && applyPreset(key)}
          >
            <span className={styles.presetIcon}>{preset.icon}</span>
            <h3>{preset.title}</h3>
            <p>{preset.description}</p>
            {settings.preset === key && <div className={styles.activeLabel}>Active Mode</div>}
          </div>
        ))}
      </section>

      <div className={styles.settingsGrid}>
        {sections.map((section) => (
          <div key={section.title} className={styles.sectionCard}>
            <h2>{section.title}</h2>
            <div className={styles.fieldsList}>
              {section.fields.map((field) => (
                <div className={styles.fieldRow} key={field.key}>
                  <div className={styles.fieldInfo}>
                    <label>{field.label}</label>
                    <span className={styles.fieldDesc}>{field.description}</span>
                  </div>
                  <input
                    type="number"
                    step={field.step}
                    className={styles.input}
                    value={settings[field.key] ?? ''}
                    onChange={(e) => updateField(field.key, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <footer className={styles.footerNote}>
        ℹ️ Changes require an engine restart to take effect.
      </footer>
    </div>
  )
}