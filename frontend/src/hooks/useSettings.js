import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '../services/api'

export function useSettings() {
  return useQuery({
    queryKey: ['settings', 'thresholds'],
    queryFn: async () => (await api.get('/settings/thresholds')).data,
  })
}

export function useSaveSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => (await api.patch('/settings/thresholds', payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'thresholds'] })
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      toast.success('Settings saved successfully')
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useRegenerateKey() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post('/settings/regenerate-key')).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings', 'thresholds'] })
      toast.success('API key regenerated')
    },
    onError: (error) => toast.error(error.message),
  })
}
