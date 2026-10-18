import { useEffect, useRef, useState } from 'react'
import { staffRequestBlob } from '../../../lib/api'
import { ErrorBlock } from '../../../components/ui'
import { OriginalVideo } from '../../events/hackathonSubmissions/OriginalVideo'
import type { Scope } from '../hackathonJudging/types'

export async function downloadProgrammeFile(path: string, filename: string) {
  const blob = await staffRequestBlob(path)
  const url = URL.createObjectURL(blob), link = document.createElement('a')
  link.href = url; link.download = filename; link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}
/** Every click reaches the server's current assignment/track/conflict check. */
export function StaffProjectFiles({ scope, assetIds, purpose: _purpose, snapshotId: _snapshotId }: { scope: Scope; assetIds: number[]; purpose: 'judge' | 'sponsor'; snapshotId?: number }) {
  return <section className="grid gap-3" aria-label="Private project files"><h3 className="font-semibold">Project files</h3>
    {assetIds.length ? <table className="w-full text-left text-sm"><caption className="sr-only">Files authorized for this assignment</caption>
      <thead><tr><th scope="col">File</th><th scope="col">Read</th></tr></thead><tbody>{assetIds.map(id => <StaffFile key={id} eventId={scope.eventId} assetId={id} />)}</tbody></table>
      : <p className="text-sm text-muted">This project has no shared files.</p>}
  </section>
}
function StaffFile({ eventId, assetId }: { eventId: number; assetId: number }) {
  const [error, setError] = useState<unknown>(null), [pending, setPending] = useState(false), [original, setOriginal] = useState<Blob | null>(null)
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  const path = `/admin/events/${eventId}/assets/${assetId}/download/`
  async function open() {
    setError(null); setPending(true); controller.current?.abort(); controller.current = new AbortController()
    try { setOriginal(await staffRequestBlob(path, { signal: controller.current.signal })) }
    catch (cause) { if (!controller.current.signal.aborted) setError(cause) }
    finally { if (!controller.current.signal.aborted) setPending(false) }
  }
  return <tr><th scope="row" className="font-normal">Project file {assetId}</th><td className="grid gap-3 p-2">
    <div className="flex flex-wrap gap-3"><button className="desk-button" disabled={pending} onClick={() => void open()}>Open original file {assetId}</button>
      <button className="desk-button" disabled={pending} onClick={() => void downloadProgrammeFile(path, `project-file-${assetId}`).catch(setError)}>Download original file {assetId}</button></div>
    {original && /^video\//.test(original.type) ? <OriginalVideo bytes={original.size} playable={/^(video\/(mp4|webm))$/.test(original.type)}
      label={`Project demonstration ${assetId}`} load={async () => original} download={() => void downloadProgrammeFile(path, `project-file-${assetId}`).catch(setError)} />
      : original ? <p className="text-sm text-muted">This original is available as a download. Its maker editor can open the source file.</p> : null}
    <ErrorBlock error={error} />
  </td></tr>
}
