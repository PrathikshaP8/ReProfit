import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { api } from '../services/api'

const INVALIDATION_KEYS = [
  ['dashboard', 'summary'],
  ['dashboard', 'trend'],
  ['dashboard', 'recent-decisions'],
  ['analytics', 'daily-profit'],
  ['analytics', 'category-breakdown'],
]

export function useReturns(status = 'all') {
  return useQuery({
    queryKey: ['returns', status],
    queryFn: async () => (await api.get('/returns', { params: { status } })).data,
  })
}

export function usePredictCondition() {
  return useMutation({
    mutationFn: async ({ id, image }) => {
      const formData = new FormData()
      formData.append('image', image)
      if (id != null) formData.append('item_id', id)
      return (
        await api.post('/returns/predict-condition', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000,
        })
      ).data
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useAnalyzeReturn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, formData }) =>
      (
        await api.post(`/returns/${id}/analyze`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000,
        })
      ).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      queryClient.invalidateQueries({ queryKey: ['analytics', 'condition-distribution'] })
      toast.success('AI analysis complete')
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useApproveReturn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }) => (await api.post(`/returns/${id}/approve`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      INVALIDATION_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: key }))
      toast.success('Return approved successfully')
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useRejectReturn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, payload }) => (await api.post(`/returns/${id}/reject`, payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      INVALIDATION_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: key }))
      toast.success('Return rejected')
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useDeleteReturn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id) => (await api.delete(`/returns/${id}`)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      INVALIDATION_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: key }))
      toast.success('Return deleted')
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useCreateReturn() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => (await api.post('/returns', payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
    },
  })
}

export function useEbaySearch() {
  return useMutation({
    mutationFn: async (query) => (await api.get('/returns/ebay/search', { params: { query, limit: 10 } })).data,
    onError: (error) => toast.error(error.message),
  })
}

export function useMarketSearch() {
  return useMutation({
    mutationFn: async (query) => (await api.get('/returns/market/search', { params: { query, limit: 10 } })).data,
    onError: (error) => toast.error(error.message),
  })
}

export function useImportEbayItem() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => (await api.post('/ebay/import', payload)).data,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      toast.success('Market listing imported into the return queue')
    },
    onError: (error) => toast.error(error.message),
  })
}

export function useAutoProcess() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async () => (await api.post('/returns/auto-process', {})).data,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['returns'] })
      INVALIDATION_KEYS.forEach((key) => queryClient.invalidateQueries({ queryKey: key }))
      toast.success(`Auto-approved ${data.auto_approved_count} items`)
    },
    onError: (error) => toast.error(error.message),
  })
}
