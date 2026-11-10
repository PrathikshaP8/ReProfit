import { useEffect, useState } from 'react'

const STORAGE_KEY = 'reprofit-theme'

function applyThemeClass(theme) {
  const root = document.documentElement
  root.classList.remove('dark', 'light')
  root.classList.add(theme)
}

export function useTheme() {
  const [theme, setTheme] = useState('dark')

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY)
    const initial = saved === 'light' || saved === 'dark' ? saved : 'dark'
    setTheme(initial)
    applyThemeClass(initial)
  }, [])

  useEffect(() => {
    if (theme !== 'dark' && theme !== 'light') return
    localStorage.setItem(STORAGE_KEY, theme)
    applyThemeClass(theme)
  }, [theme])

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))

  return { theme, setTheme, toggleTheme }
}

