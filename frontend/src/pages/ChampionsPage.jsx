import { useNavigate } from 'react-router-dom'
import ChampionGrid from '../components/ChampionGrid'
import { number } from '../format'

export default function ChampionsPage({ champions, loading, error, totalGames }) {
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
    <>
      <ChampionGrid
        champions={champions}
        onSelect={(c) => navigate(`/champions/${c.championId}`)}
      />
      {totalGames != null && (
        <p className="games-parsed">
          {number(totalGames)} total {totalGames === 1 ? 'game' : 'games'} parsed
        </p>
      )}
    </>
  )
}
