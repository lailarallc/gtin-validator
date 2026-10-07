import type { DataCompleteness, SampleData, SummaryResponse, ValidationResponse } from './types'

const BASE = import.meta.env.VITE_API_URL || ''

class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30_000)
  try {
    const res = await fetch(`${BASE}${url}`, { ...init, signal: controller.signal })
    if (!res.ok) {
      const text = await res.text()
      throw new ApiError(res.status, text)
    }
    return res.json()
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error('Request timed out — the server may be starting up. Try again in a moment.')
    }
    throw e
  } finally {
    clearTimeout(timeout)
  }
}

export async function validateGtins(gtins: string[]): Promise<SummaryResponse> {
  return request('/api/validate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gtins }),
  })
}

export async function validateUpload(
  file: File,
  gtinColumn?: string,
): Promise<SummaryResponse> {
  const form = new FormData()
  form.append('file', file)
  const params = gtinColumn ? `?gtin_column=${encodeURIComponent(gtinColumn)}` : ''
  return request(`/api/validate/upload${params}`, {
    method: 'POST',
    body: form,
  })
}

export async function runSample(): Promise<ValidationResponse> {
  return request('/api/sample/validate', { method: 'POST' })
}

export async function fetchSampleData(): Promise<SampleData> {
  return request('/api/sample')
}

export async function fetchRetailers(): Promise<Record<string, { description: string; notes: string }>> {
  return request('/api/retailers')
}

export async function fetchCompleteness(token: string): Promise<DataCompleteness> {
  return request(`/api/completeness/${token}`)
}

async function downloadBlob(url: string): Promise<Blob> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 30_000)
  try {
    const res = await fetch(`${BASE}${url}`, { signal: controller.signal })
    if (!res.ok) throw new ApiError(res.status, await res.text())
    return res.blob()
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error('Request timed out — the server may be starting up. Try again in a moment.')
    }
    throw e
  } finally {
    clearTimeout(timeout)
  }
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export async function downloadCsvReport(token: string, companyName: string) {
  const name = companyName.replace(/ /g, '_') || 'gtin'
  const blob = await downloadBlob(`/api/reports/csv/${token}?company_name=${encodeURIComponent(companyName)}`)
  triggerDownload(blob, `${name}_report.csv`)
}

export async function downloadCorrectedCsv(token: string, companyName: string) {
  const name = companyName.replace(/ /g, '_') || 'gtin'
  const blob = await downloadBlob(`/api/reports/corrected/${token}?company_name=${encodeURIComponent(companyName)}`)
  triggerDownload(blob, `${name}_corrected.csv`)
}

export async function downloadPdfReport(token: string, companyName: string) {
  const name = companyName.replace(/ /g, '_') || 'gtin'
  const blob = await downloadBlob(`/api/reports/pdf/${token}?company_name=${encodeURIComponent(companyName)}`)
  triggerDownload(blob, `${name}_report.pdf`)
}
