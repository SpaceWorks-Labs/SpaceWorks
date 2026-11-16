import { t } from "@lingui/core/macro";
import { decryptBytes, deleteScopes, encryptBytes, expired, keyFor, openEncryptedDatabase, readKey, requestValue, transactionDone, type Ciphertext } from '../../../lib/encryptedIndexedDb'

const DB = 'spaceworks-mentor-round-drafts-v1'
type RecordValue = { id: string; scope: string; closesAt: string; encrypted: Ciphertext }
async function database() { return openEncryptedDatabase(DB, 1, [{ name: 'keys' }, { name: 'drafts', keyPath: 'id' }]) }
export async function saveRoundDraft(scope: string, teamId: number, closesAt: string, answers: Record<string, unknown>) {
  if (expired(closesAt)) throw new Error(t`This round has closed. The draft cannot be saved.`)
  const bytes = new TextEncoder().encode(JSON.stringify(answers))
  if (bytes.byteLength > 64_000) throw new Error(t`Keep this visit draft below 64 KB.`)
  const db = await database()
  try {
    const id = `${scope}:${teamId}`
    const key = await keyFor(db, scope)
    const encrypted = await encryptBytes(key, bytes.buffer, id)
    const tx = db.transaction('drafts', 'readwrite')
    const done = transactionDone(tx)
    tx.objectStore('drafts').put({ id, scope, closesAt, encrypted } satisfies RecordValue)
    await done
  } finally { db.close() }
}

export async function readRoundDraft(scope: string, teamId: number): Promise<Record<string, unknown> | null> {
  const db = await database()
  try {
    const id = `${scope}:${teamId}`
    const row = await requestValue<RecordValue | undefined>(db.transaction('drafts').objectStore('drafts').get(id))
    if (!row) return null
    if (expired(row.closesAt)) { await deleteScopes(db, ['drafts'], [scope]); return null }
    const key = await readKey(db, scope)
    if (!key) return null
    return JSON.parse(new TextDecoder().decode(await decryptBytes(key, row.encrypted, id))) as Record<string, unknown>
  } finally { db.close() }
}

export async function clearRoundDrafts(scope: string) {
  const db = await database()
  try { await deleteScopes(db, ['drafts'], [scope]) } finally { db.close() }
}
