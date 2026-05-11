const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function getAttendanceLogs({ limit = 50, offset = 0 } = {}) {
  const response = await fetch(
    `${API_BASE_URL}/attendance-logs?limit=${limit}&offset=${offset}`
  )

  if (!response.ok) {
    throw new Error('Failed to fetch attendance logs')
  }

  return response.json()
}