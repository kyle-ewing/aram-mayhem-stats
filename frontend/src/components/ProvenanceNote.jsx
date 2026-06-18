// Honest, short statement about where the numbers come from.
export default function ProvenanceNote() {
  return (
    <p className="provenance">
      Winrates come from community-run LCU collectors (first-party game client
      data), not the Riot API. Low sample sizes mean low confidence, treat
      small-sample numbers with caution.
    </p>
  )
}
