import { useEffect, useState } from 'react'

interface Stats {
  short_code: string
  long_url: string
  total_clicks: number
  created_at: string
  clicks_by_day: { day: string; count: number }[]
  top_referrers: { referrer: string; count: number }[]
  top_browsers: { browser: string; count: number }[]
}

export function StatsDashboard({ code }: { code: string }) {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const res = await fetch(`/api/urls/${code}/stats`)
        if (cancelled) return
        if (res.status === 404) {
          setError('not_found')
          setLoading(false)
          return
        }
        if (!res.ok) {
          setError(`HTTP ${res.status}`)
          setLoading(false)
          return
        }
        setStats((await res.json()) as Stats)
        setLoading(false)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Unknown error')
          setLoading(false)
        }
      }
    }
    load()
    return () => {
      cancelled = true
    }
  }, [code])

  if (loading) return <div data-testid="loading">Loading…</div>
  if (error) return <div role="alert" data-testid="error">{error}</div>
  if (!stats) return null

  const maxDay = Math.max(...stats.clicks_by_day.map((d) => d.count), 1)

  return (
    <div data-testid="stats">
      <h2 data-testid="short-code">{stats.short_code}</h2>
      <div>
        Long URL: <span data-testid="long-url">{stats.long_url}</span>
      </div>
      <div>
        Total clicks: <strong data-testid="total-clicks">{stats.total_clicks}</strong>
      </div>

      <h3>Clicks by day (last 30)</h3>
      <div data-testid="clicks-by-day">
        {stats.clicks_by_day.length === 0 ? (
          <div>No clicks yet.</div>
        ) : (
          stats.clicks_by_day.map((d) => (
            <div key={d.day} className="bar-row">
              <span className="bar-label">{d.day}</span>
              <div
                className="bar"
                style={{ width: `${(d.count / maxDay) * 200}px` }}
              />
              <span className="bar-value">{d.count}</span>
            </div>
          ))
        )}
      </div>

      <h3>Top referrers</h3>
      <ul data-testid="top-referrers">
        {stats.top_referrers.map((r) => (
          <li key={r.referrer}>
            {r.referrer}: {r.count}
          </li>
        ))}
      </ul>

      <h3>Top browsers</h3>
      <ul data-testid="top-browsers">
        {stats.top_browsers.map((b) => (
          <li key={b.browser}>
            {b.browser}: {b.count}
          </li>
        ))}
      </ul>
    </div>
  )
}