import dayjs from 'dayjs'
import relativeTime from 'dayjs/plugin/relativeTime'

dayjs.extend(relativeTime)

export function formatDateTime(value) {
  if (!value) return '--'
  const d = dayjs(value)
  return d.isValid() ? d.format('DD MMM YYYY, h:mm A') : '--'
}

export function timeFromNow(value) {
  if (!value) return '--'
  const d = dayjs(value)
  return d.isValid() ? d.fromNow() : '--'
}

