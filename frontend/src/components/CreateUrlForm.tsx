import { useState } from 'react'

interface CreatedUrl {
  short_code: string
  short_url: string
  long_url: string
  created_at: string
}

export function CreateUrlForm({
  onCreated,
}: {
  onCreated: (code: string) => void
}) {
  const [longUrl, setLongUrl] = useState('')
  const [customCode, setCustomCode] = useState('')
  const [result, setResult] = useState<CreatedUrl | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const body: { long_url: string; custom_code?: string } = { long_url: longUrl }
      if (customCode) body.custom_code = customCode

      const res = await fetch('/api/urls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })

      if (!res.ok) {
        const err = (await res.json().catch(() => ({}))) as { detail?: string }
        setError(err.detail ?? `HTTP ${res.status}`)
        return
      }

      const data = (await res.json()) as CreatedUrl
      setResult(data)
      onCreated(data.short_code)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} data-testid="create-form">
      <label>
        Long URL
        <input
          type="url"
          value={longUrl}
          onChange={(e) => setLongUrl(e.target.value)}
          placeholder="https://example.com/some/long/path"
          required
          data-testid="long-url"
        />
      </label>
      <label>
        Custom code (optional, 3-32 chars, [A-Za-z0-9_-])
        <input
          value={customCode}
          onChange={(e) => setCustomCode(e.target.value)}
          placeholder="docs"
          pattern="[A-Za-z0-9_\-]{3,32}"
          data-testid="custom-code"
        />
      </label>
      <button type="submit" disabled={loading} data-testid="submit">
        {loading ? 'Shortening…' : 'Shorten'}
      </button>
      {error && (
        <div role="alert" data-testid="error">
          {error}
        </div>
      )}
      {result && (
        <div data-testid="result">
          <div>
            Short URL:{' '}
            <a href={result.short_url} data-testid="short-url">
              {result.short_url}
            </a>
          </div>
          <div>
            Code: <code data-testid="short-code">{result.short_code}</code>
          </div>
        </div>
      )}
    </form>
  )
}