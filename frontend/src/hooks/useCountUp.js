import { useEffect, useState } from 'react'

export function useCountUp(target, duration = 1200) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    const finalValue = Number(target) || 0
    let start = 0
    const startTs = performance.now()

    const frame = (now) => {
      const progress = Math.min((now - startTs) / duration, 1)
      start = finalValue * progress
      setValue(start)
      if (progress < 1) requestAnimationFrame(frame)
    }

    setValue(0)
    const id = requestAnimationFrame(frame)
    return () => cancelAnimationFrame(id)
  }, [target, duration])

  return value
}

