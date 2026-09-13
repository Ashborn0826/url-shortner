import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StatsDashboard } from './StatsDashboard'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('StatsDashboard', () => {
  it('renders total + day bars + top lists after loading', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              short_code: 'abc1234',
              long_url: 'https://example.com',
              total_clicks: 42,
              created_at: '2026-09-12T10:00:00Z',
              clicks_by_day: [
                { day: '2026-09-12', count: 30 },
                { day: '2026-09-11', count: 12 },
              ],
              top_referrers: [
                { referrer: 'google.com', count: 30 },
                { referrer: '(direct)', count: 12 },
              ],
              top_browsers: [
                { browser: 'Chrome', count: 42 },
              ],
            }),
        } as Response),
      ),
    )

    render(<StatsDashboard code="abc1234" />)

    expect(screen.getByTestId('loading')).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByTestId('stats')).toBeInTheDocument()
    })

    expect(screen.getByTestId('total-clicks')).toHaveTextContent('42')
    expect(screen.getByTestId('short-code')).toHaveTextContent('abc1234')
    expect(screen.getByTestId('long-url')).toHaveTextContent('https://example.com')

    expect(screen.getByText('google.com: 30')).toBeInTheDocument()
    expect(screen.getByText('(direct): 12')).toBeInTheDocument()
    expect(screen.getByText('Chrome: 42')).toBeInTheDocument()
  })

  it('shows not_found on 404', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({ ok: false, status: 404 } as Response),
      ),
    )

    render(<StatsDashboard code="missing" />)

    await waitFor(() => {
      expect(screen.getByTestId('error')).toHaveTextContent('not_found')
    })
  })

  it('renders the empty state when there are no clicks', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              short_code: 'fresh',
              long_url: 'https://example.com',
              total_clicks: 0,
              created_at: '2026-09-12T10:00:00Z',
              clicks_by_day: [],
              top_referrers: [],
              top_browsers: [],
            }),
        } as Response),
      ),
    )

    render(<StatsDashboard code="fresh" />)

    await waitFor(() => {
      expect(screen.getByTestId('stats')).toBeInTheDocument()
    })

    expect(screen.getByTestId('total-clicks')).toHaveTextContent('0')
    expect(screen.getByText('No clicks yet.')).toBeInTheDocument()
  })
})