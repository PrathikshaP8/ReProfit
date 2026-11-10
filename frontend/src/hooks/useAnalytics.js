import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export function useDailyProfit(range) {
  return useQuery({
    queryKey: ['analytics', 'daily-profit', range],
    queryFn: async () => (await api.get('/analytics/daily-profit', { params: { range } })).data,
  })
}

export function useCategoryBreakdown(range) {
  return useQuery({
    queryKey: ['analytics', 'category-breakdown', range],
    queryFn: async () => (await api.get('/analytics/category-breakdown', { params: { range } })).data,
  })
}

export function useConditionDistribution(range) {
  return useQuery({
    queryKey: ['analytics', 'condition-distribution', range],
    queryFn: async () => (await api.get('/analytics/condition-distribution', { params: { range } })).data,
  })
}
