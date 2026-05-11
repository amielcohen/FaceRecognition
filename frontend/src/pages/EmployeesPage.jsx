import { useEffect, useState } from 'react'
import styles from './EmployeesPage.module.css'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default function EmployeesPage() {
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')

  const [isRebuilding, setIsRebuilding] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  async function loadEmployees() {
    try {
      setLoading(true)
      setError('')
      const response = await fetch(`${API_BASE_URL}/employees`)
      if (!response.ok) throw new Error('Failed to load employees')
      const data = await response.json()
      setEmployees(data.items || [])
    } catch (err) {
      console.error(err)
      setError('Failed to load employees')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadEmployees()
  }, [])

  async function handleAddEmployee(e) {
    e.preventDefault()
    try {
      setError('')
      const response = await fetch(`${API_BASE_URL}/employees`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          first_name: firstName,
          last_name: lastName,
        }),
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Failed to create employee')
      setFirstName('')
      setLastName('')
      loadEmployees()
    } catch (err) {
      setError(err.message)
    }
  }

 async function handleRebuildEmbeddings() {
  try {
    setError('')
    setSuccessMessage('')
    setIsRebuilding(true)

    const response = await fetch(`${API_BASE_URL}/rebuild-embeddings`, {
      method: 'POST',
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'Failed to rebuild embeddings')
    }

    setSuccessMessage('Embeddings rebuilt successfully. Restart recognition process if live recognition is already running.')
  } catch (err) {
    console.error(err)
    setError(err.message)
  } finally {
    setIsRebuilding(false)
  }
}


  async function handleDeleteEmployee(folderName) {
    if (!window.confirm(`Are you sure you want to delete ${folderName}?`)) return
    try {
      const response = await fetch(`${API_BASE_URL}/employees/${folderName}`, {
        method: 'DELETE',
      })
      if (!response.ok) throw new Error('Failed to delete employee')
      loadEmployees()
    } catch (err) {
      setError('Failed to delete employee')
    }
  }

  async function handleUploadImages(event, folderName) {
    const files = event.target.files
    if (!files || files.length === 0) return
    try {
      const formData = new FormData()
      for (const file of files) formData.append('files', file)
      const response = await fetch(`${API_BASE_URL}/employees/${folderName}/images`, {
        method: 'POST',
        body: formData,
      })
      if (!response.ok) throw new Error('Failed to upload images')
      loadEmployees()
    } catch (err) {
      setError('Failed to upload images')
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.topSection}>
        <div>
          <h1>Employees</h1>
          <p>Manage employees, training images, and recognition identities.</p>
        </div>
        <button 
           className={styles.rebuildButton}
            onClick={handleRebuildEmbeddings}
            disabled={isRebuilding}>
           {isRebuilding ? (<>
              <span className={styles.spinner}></span>
            Rebuilding...</>) : (
          'Rebuild Embeddings')}
        </button>
      </div>

      <div className={styles.actionToolbar}>
        <form className={styles.addForm} onSubmit={handleAddEmployee}>
          <div className={styles.inputGroup}>
            <input
              type="text"
              placeholder="First Name"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              required
              className={styles.input}
            />
            <input
              type="text"
              placeholder="Last Name"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              required
              className={styles.input}
            />
          </div>
          <button type="submit" className={styles.addButton}>
            + Add Employee
          </button>
        </form>
      </div>

      {error && <div className={styles.errorCard}>⚠️ {error}</div>}

      {loading ? (
        <div className={styles.loadingState}>Loading employee directory...</div>
      ) : employees.length === 0 ? (
        <div className={styles.emptyState}>No employees registered yet.</div>
      ) : (
        <div className={styles.tableWrapper}>
          {successMessage && (
  <div className={styles.success}>{successMessage}</div>
)}
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Profile</th>
                <th>Full Name</th>
                <th>Folder ID</th>
                <th>Training Samples</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((employee) => (
                <tr key={employee.folder_name} className={styles.tableRow}>
                  <td className={styles.imageCell}>
                    {employee.preview_image ? (
                      <img
                        src={`${API_BASE_URL}/${employee.preview_image}`}
                        alt={employee.display_name}
                        className={styles.avatar}
                      />
                    ) : (
                      <div className={styles.avatarPlaceholder}>
                        {employee.display_name?.charAt(0) || '?'}
                      </div>
                    )}
                  </td>
                  <td className={styles.nameCell}>{employee.display_name}</td>
                  <td className={styles.folderCell}><code>{employee.folder_name}</code></td>
                  <td>
                    <span className={styles.countBadge}>
                      {employee.images_count} images
                    </span>
                  </td>
                  <td>
                    <div className={styles.actions}>
                      <label className={styles.uploadBtn}>
                        Upload
                        <input
                          type="file"
                          multiple
                          hidden
                          accept="image/*"
                          onChange={(e) => handleUploadImages(e, employee.folder_name)}
                        />
                      </label>
                      <button
                        className={styles.deleteBtn}
                        onClick={() => handleDeleteEmployee(employee.folder_name)}
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}