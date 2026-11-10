import { Moon, Sun } from 'lucide-react'
import { useTheme } from '../hooks/useTheme'

export default function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()

  return (
    <button
      type="button"
      onClick={toggleTheme}
      className="flex h-11 w-11 items-center justify-center rounded-lg border transition-transform hover:scale-105"
      style={{ background: 'var(--bg-card)', borderColor: 'var(--border-color)' }}
      aria-label="Toggle theme"
    >
      <span className="transition-all duration-200">
        {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
      </span>
    </button>
  )
}

