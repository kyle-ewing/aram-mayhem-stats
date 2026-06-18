import { useNavigate } from 'react-router-dom'
import ChampionGrid from '../components/ChampionGrid'

export default function ChampionsPage({ champions, loading, error }) {
  const navigate = useNavigate()

  if (loading) return <p className="status">Loading champions...</p>
  if (error) {
    return (
      <p className="status error" role="alert">
        {error}
      </p>
    )
  }

  return (
    <ChampionGrid
      champions={champions}
      onSelect={(c) => navigate(`/champions/${c.championId}`)}
    />
  )
}
