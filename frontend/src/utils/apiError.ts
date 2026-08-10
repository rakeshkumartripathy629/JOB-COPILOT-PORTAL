import { AxiosError } from 'axios'

export function getApiError(error: unknown): string {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      const first = detail[0]
      if (first && typeof first === 'object' && 'msg' in first) return String(first.msg)
    }
    return error.message
  }
  return error instanceof Error ? error.message : 'Something went wrong'
}
