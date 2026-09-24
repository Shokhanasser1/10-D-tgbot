import { useState } from 'react'

import styles from './ImageCarousel.module.css'

interface ImageCarouselProps {
  images: string[]
  alt: string
}

export function ImageCarousel({ images, alt }: ImageCarouselProps) {
  const [activeIndex, setActiveIndex] = useState(0)

  if (images.length === 0) {
    return <div className={styles.placeholder} />
  }

  return (
    <div className={styles.carousel}>
      <div
        className={styles.track}
        onScroll={(event) => {
          const target = event.currentTarget
          const index = Math.round(target.scrollLeft / target.clientWidth)
          setActiveIndex(index)
        }}
      >
        {images.map((url, index) => (
          <img key={url} src={url} alt={`${alt} ${index + 1}`} className={styles.image} />
        ))}
      </div>
      {images.length > 1 && (
        <div className={styles.dots}>
          {images.map((url, index) => (
            <span
              key={url}
              className={[styles.dot, index === activeIndex ? styles.dotActive : ''].join(' ')}
            />
          ))}
        </div>
      )}
    </div>
  )
}
