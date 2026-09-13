import { useState } from 'react'
import { CreateUrlForm } from './components/CreateUrlForm'
import { StatsDashboard } from './components/StatsDashboard'
import './App.css'

function App() {
  const [code, setCode] = useState<string | null>(null)

  return (
    <div className="container">
      <h1>URL Shortener</h1>
      {code === null ? (
        <CreateUrlForm onCreated={setCode} />
      ) : (
        <>
          <button
            type="button"
            className="back"
            onClick={() => setCode(null)}
            data-testid="back"
          >
            ← Create another
          </button>
          <StatsDashboard code={code} />
        </>
      )}
    </div>
  )
}

export default App