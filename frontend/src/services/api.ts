import axios, { type AxiosRequestConfig } from 'axios'
import { useAuthStore } from '../store/authStore'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8001',
  withCredentials: true,
})

let refreshPromise: Promise<string | null> | null = null

async function tryRefresh(): Promise<string | null> {
  try {
    const { data } = await axios.post<{ access_token: string }>(
      `${api.defaults.baseURL}/auth/refresh`,
      {},
      { withCredentials: true }
    )
    useAuthStore.getState().setToken(data.access_token)
    return data.access_token
  } catch {
    return null
  }
}

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error?.config as (AxiosRequestConfig & { _retry?: boolean }) | undefined
    if (error?.response?.status === 401 && original && !original._retry) {
      original._retry = true
      refreshPromise = refreshPromise ?? tryRefresh()
      const token = await refreshPromise
      refreshPromise = null
      if (token) {
        original.headers = { ...original.headers, Authorization: `Bearer ${token}` }
        return api(original)
      }
    }
    if (error?.response?.status === 401) {
      useAuthStore.getState().logout()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
