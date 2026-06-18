import RarityBadge from './RarityBadge'

// Curated editorial notes, clearly distinct from measured winrates.
export default function SynergyNotes({ synergies }) {
  if (!synergies || synergies.length === 0) return null

  return (
    <section className="synergy-notes">
      <h3>Community synergy notes</h3>
      <p className="muted">
        Curated editorial picks from the community, not measured winrates.
      </p>
      <ul className="synergy-list">
        {synergies.map((s, i) => (
          <li key={`${s.augment}-${i}`} className="synergy-item">
            <div className="synergy-head">
              <span className="synergy-augment">{s.augment}</span>
              <RarityBadge rarity={s.rarity} />
            </div>
            <p className="synergy-text">{s.note}</p>
            {s.source && (
              <a
                className="synergy-source"
                href={s.source}
                target="_blank"
                rel="noopener noreferrer"
              >
                Source
              </a>
            )}
          </li>
        ))}
      </ul>
    </section>
  )
}
