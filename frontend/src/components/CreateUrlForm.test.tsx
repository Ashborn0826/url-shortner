import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { CreateUrlForm } from './CreateUrlForm'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('CreateUrlForm', () => {
  it('submits the URL and shows the short_url + calls onCreated', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              short_code: 'abc1234',
              short_url: 'http://localhost:8000/abc1234',
              long_url: 'https://example.com',
              created_at: '2026-09-12T10:00:00Z',
            }),
        } as Response),
      ),
    )

    const onCreated = vi.fn()
    render(<CreateUrlForm onCreated={onCreated} />)

    fireEvent.change(screen.getByTestId('long-url'), {
      target: { value: 'https://example.com' },
    })
    fireEvent.click(screen.getByTestId('submit'))

    await waitFor(() => {
      expect(screen.getByTestId('result')).toBeInTheDocument()
    })

    expect(screen.getByTestId('short-url')).toHaveTextContent(
      'http://localhost:8000/abc1234',
    )
    expect(screen.getByTestId('short-code')).toHaveTextContent('abc1234')
    expect(onCreated).toHaveBeenCalledWith('abc1234')
  })

  it('includes custom_code in the request body when provided', async () => {
    const fetchMock = vi.fn(() =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve({
            short_code: 'docs',
            short_url: 'http://localhost:8000/docs',
            long_url: 'https://example.com',
            created_at: '2026-09-12T10:00:00Z',
          }),
      } as Response),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<CreateUrlForm onCreated={() => {}} />)

    fireEvent.change(screen.getByTestId('long-url'), {
      target: { value: 'https://example.com' },
    })
    fireEvent.change(screen.getByTestId('custom-code'), {
      target: { value: 'docs' },
    })
    fireEvent.click(screen.getByTestId('submit'))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled()
    })

    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const body = JSON.parse(init.body as string)
    expect(body).toEqual({ long_url: 'https://example.com', custom_code: 'docs' })
  })

  it('shows the API error detail on 4xx', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 422,
          json: () => Promise.resolve({ detail: 'invalid url' }),
        } as Response),
      ),
    )

    render(<CreateUrlForm onCreated={() => {}} />)

    // Use a URL that passes the browser's HTML5 validation; the fetch is mocked
    // to return 422 regardless of what we send, so the input value doesn't matter.
    fireEvent.change(screen.getByTestId('long-url'), {
      target: { value: 'https://example.com' },
    })
    fireEvent.click(screen.getByTestId('submit'))

    await waitFor(() => {
      expect(screen.getByTestId('error')).toHaveTextContent('invalid url')
    })
  })

  it('shows a 409 message when the custom code is taken', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 409,
          json: () => Promise.resolve({ detail: 'code_taken' }),
        } as Response),
      ),
    )

    render(<CreateUrlForm onCreated={() => {}} />)

    fireEvent.change(screen.getByTestId('long-url'), {
      target: { value: 'https://example.com' },
    })
    fireEvent.change(screen.getByTestId('custom-code'), {
      target: { value: 'taken' },
    })
    fireEvent.click(screen.getByTestId('submit'))

    await waitFor(() => {
      expect(screen.getByTestId('error')).toHaveTextContent('code_taken')
    })
  })
})