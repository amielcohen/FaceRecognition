import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import MainLayout from './layouts/MainLayout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import LiveMonitorPage from './pages/LiveMonitorPage'
import EmployeesPage from './pages/EmployeesPage'
import AttendanceLogsPage from './pages/AttendanceLogsPage'
import UnknownFacesPage from './pages/UnknownFacesPage'
import CameraSettingsPage from './pages/CameraSettingsPage'

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth()
  return isAuthenticated ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="live" element={<LiveMonitorPage />} />
            <Route path="employees" element={<EmployeesPage />} />
            <Route path="attendance" element={<AttendanceLogsPage />} />
            <Route path="alerts" element={<UnknownFacesPage />} />
            <Route path="camera-settings" element={<CameraSettingsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
