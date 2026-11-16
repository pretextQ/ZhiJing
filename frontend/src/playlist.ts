export interface Track {
  id: string
  file: File
}

function openLibrary(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('zhijing-audio', 1)
    request.onupgradeneeded = () => request.result.createObjectStore('library')
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function readTracks(): Promise<Track[]> {
  const db = await openLibrary()
  try {
    return await new Promise<Track[]>((resolve, reject) => {
      const request = db.transaction('library').objectStore('library').get('tracks')
      request.onsuccess = () => resolve(request.result ?? [])
      request.onerror = () => reject(request.error)
    })
  } finally {
    db.close()
  }
}

export async function saveTracks(tracks: Track[]): Promise<void> {
  const db = await openLibrary()
  try {
    await new Promise<void>((resolve, reject) => {
      const transaction = db.transaction('library', 'readwrite')
      transaction.objectStore('library').put(tracks, 'tracks')
      transaction.oncomplete = () => resolve()
      transaction.onabort = () => reject(transaction.error)
    })
  } finally {
    db.close()
  }
}
