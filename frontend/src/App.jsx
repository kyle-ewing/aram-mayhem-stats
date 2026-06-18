import { useEffect, useState } from 'react'
import {
  NavLink,
  Navigate,
  Route,
  Routes,
  useLocation,
} from 'react-router-dom'
import { getChampions, getSynergies } from './api'
import './App.css'
import AugmentManager from './components/AugmentManager'
import ProvenanceNote from './components/ProvenanceNote'
import ChampionDetailPage from './pages/ChampionDetailPage'
import ChampionsPage from './pages/ChampionsPage'

export default function App() {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [champions, setChampions] = useState([])
  const [synergies, setSynergies] = useState([])

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)

    Promise.all([getChampions(), getSynergies()])
      .then(([champs, syns]) => {
        if (!active) return
        setChampions(champs ?? [])
        setSynergies(syns ?? [])
      })
      .catch((err) => {
        if (active) setError(err.message || 'Something went wrong.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })

    return () => {
      active = false
    }
  }, [])

  const { pathname } = useLocation()
  // Keep "Champions" highlighted on the champion detail pages, which live under
  // it, not just on the exact "/" route.
  const championsActive = pathname === '/' || pathname.startsWith('/champions')
  const navClass = ({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')

  return (
    <div className="app">
      <header className="app-header">
        <h1>ARAM Mayhem Augment Statistics</h1>
        <p className="subtitle">
          Pick a champion to see its ARAM Mayhem augment win rates, overall win
          rate and sample size, plus curated synergy notes.
        </p>
        <nav className="app-nav">
          <NavLink
            to="/"
            end
            className={championsActive ? 'nav-link active' : 'nav-link'}
          >
            Champions
          </NavLink>
          <NavLink to="/augments" className={navClass}>
            Manage augments
          </NavLink>
        </nav>
      </header>

      <main>
        <Routes>
          <Route
            path="/"
            element={
              <ChampionsPage
                champions={champions}
                loading={loading}
                error={error}
              />
            }
          />
          <Route
            path="/champions/:championId"
            element={
              <ChampionDetailPage
                champions={champions}
                synergies={synergies}
                loading={loading}
              />
            }
          />
          <Route path="/augments" element={<AugmentManager />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>

      <footer className="app-footer">
        <ProvenanceNote />
      </footer>
    </div>
  )
}
