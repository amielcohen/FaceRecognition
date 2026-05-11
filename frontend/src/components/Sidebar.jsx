import { NavLink } from 'react-router-dom'
import styles from './Sidebar.module.css'

const NAV_ITEMS = [
  { to: '/dashboard',       label: 'Dashboard',        icon: '⬡' },
  { to: '/live',            label: 'Live Monitor',     icon: '◉' },
  { to: '/employees',       label: 'Employees',        icon: '▣' },
  { to: '/attendance',      label: 'Attendance Logs',  icon: '≡' },
  { to: '/alerts',          label: 'Unknown / Alerts', icon: '⚠' },
  { to: '/camera-settings', label: 'Camera Settings',  icon: '◈' },
]

export default function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span className={styles.logoIcon}>◉</span>
        <span className={styles.logoText}>FaceRec</span>
      </div>

      <nav className={styles.nav}>
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `${styles.item} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.icon}>{icon}</span>
            <span className={styles.label}>{label}</span>
          </NavLink>
        ))}
      </nav>

      <div className={styles.footer}>
        <div className={styles.statusDot} />
        <span className={styles.statusText}>System Online</span>
      </div>
    </aside>
  )
}
