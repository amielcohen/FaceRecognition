import { useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import styles from './Header.module.css'

const PAGE_TITLES = {
  '/dashboard':       'Dashboard',
  '/live':            'Live Monitor',
  '/employees':       'Employees',
  '/attendance':      'Attendance Logs',
  '/alerts':          'Unknown / Alerts',
  '/camera-settings': 'Camera Settings',
}

export default function Header() {
  const { pathname } = useLocation()
  const { logout } = useAuth()
  const title = PAGE_TITLES[pathname] ?? 'FaceRec'

  return (
    <header className={styles.header}>
      <h1 className={styles.title}>{title}</h1>
      <button className={styles.logout} onClick={logout}>
        Logout
      </button>
    </header>
  )
}
