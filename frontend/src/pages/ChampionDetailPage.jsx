import { useNavigate, useParams } from 'react-router-dom'
import ChampionDetail from '../components/ChampionDetail'

export default function ChampionDetailPage({ champions, synergies, loading }) {
  const { championId } = useParams()
  const navigate = useNavigate()

  // The grid passes a numeric id into the URL; useParams hands it back as a
  // string, so compare loosely to find the matching leaderboard summary (used
  // for instant display before the detail fetch resolves, and on deep links it
  // may simply be absent).
  const summary = (champions ?? []).find(
    (c) => String(c.championId) === String(championId),
  )

  if (loading && !summary) {
    return <p className="status">Loading champion...</p>
  }

  return (
    <ChampionDetail
      championId={championId}
      summary={summary ?? null}
      synergies={synergies}
      onBack={() => navigate('/')}
    />
  )
}
