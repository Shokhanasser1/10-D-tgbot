/** "14:05" in the viewer's own time zone, spelled for the current language. */
export function formatClock(isoTimestamp: string, language: string): string {
  return new Intl.DateTimeFormat(language, { hour: '2-digit', minute: '2-digit' }).format(
    new Date(isoTimestamp),
  )
}
