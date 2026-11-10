import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export function useDashboardSummary() {
  return useQuery({
    queryKey: ['dashboard', 'summary'],
    queryFn: async () => (await api.get('/dashboard/summary')).data,
  })
}

export function useDashboardTrend(period) {
  return useQuery({
    queryKey: ['dashboard', 'trend', period],
    queryFn: async () => (await api.get('/dashboard/trend', { params: { period } })).data,
  })
}

export function useDecisionSplit() {
  return useQuery({
    queryKey: ['dashboard', 'decision-split'],
    queryFn: async () => (await api.get('/dashboard/decision-split')).data,
  })
}

export function useRecentDecisions() {
  return useQuery({
    queryKey: ['dashboard', 'recent-decisions'],
    queryFn: async () => (await api.get('/dashboard/recent-decisions')).data,
  })
}

