import { useState } from 'react'

// Renders an icon image, hiding itself if the url is missing or fails to load.
export default function Icon({ url, className }) {
  const [hidden, setHidden] = useState(false)
  if (hidden || !url) return null
  return (
    <img
      className={className}
      src={url}
      alt=""
      loading="lazy"
      onError={() => setHidden(true)}
    />
  )
}
