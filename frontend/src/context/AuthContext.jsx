import { createContext, useContext, useState } from 'react'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [isAuthenticated, setIsAuthenticated] = useState(
    () => localStorage.getItem('auth') === 'true'
  )

  function login(username, password) {
    // TODO: replace with real API call
    if (username === 'admin' && password === 'admin') {
      localStorage.setItem('auth', 'true')
      setIsAuthenticated(true)
      return true
    }
    return false
  }

  function logout() {
    localStorage.removeItem('auth')
    setIsAuthenticated(false)
  }

  return (
    <AuthContext.Provider value={{ isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
