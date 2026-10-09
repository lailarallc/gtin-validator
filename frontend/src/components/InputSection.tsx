import { useCallback, useRef, useState } from 'react'
import * as api from '../api'
import type { AppAction, AppState } from '../types'
import styles from './InputSection.module.css'

interface Props {
  state: AppState
  dispatch: React.Dispatch<AppAction>
}

export default function InputSection({ state, dispatch }: Props) {
  const fileRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [pasteText, setPasteText] = useState('')

  const handleFile = useCallback(
    async (file: File) => {
      dispatch({ type: 'VALIDATION_START' })
      try {
        const data = await api.validateUpload(file)
        dispatch({ type: 'VALIDATION_SUCCESS', data })
      } catch (e) {
        dispatch({
          type: 'VALIDATION_ERROR',
          error: e instanceof Error ? e.message : 'Upload failed',
        })
      }
    },
    [dispatch],
  )

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      setDragOver(false)
      const file = e.dataTransfer.files[0]
      if (file) handleFile(file)
    },
    [handleFile],
  )

  const [pasteError, setPasteError] = useState('')

  const handlePaste = useCallback(async () => {
    const lines = pasteText
      .trim()
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    if (!lines.length) {
      setPasteError('Paste some GTINs first — one per line.')
      return
    }
    setPasteError('')
    dispatch({ type: 'VALIDATION_START' })
    try {
      const data = await api.validateGtins(lines.slice(0, 10_000))
      dispatch({ type: 'VALIDATION_SUCCESS', data })
    } catch (e) {
      dispatch({
        type: 'VALIDATION_ERROR',
        error: e instanceof Error ? e.message : 'Validation failed',
      })
    }
  }, [pasteText, dispatch])

  const handleSample = useCallback(async () => {
    dispatch({ type: 'SET_INPUT_METHOD', method: 'sample' })
    dispatch({ type: 'VALIDATION_START' })
    try {
      const data = await api.runSample()
      dispatch({ type: 'VALIDATION_SUCCESS', data })
    } catch (e) {
      dispatch({
        type: 'VALIDATION_ERROR',
        error: e instanceof Error ? e.message : 'Failed to load sample data',
      })
    }
  }, [dispatch])

  return (
    <section>
      <div className={styles.buttons}>
        <button
          className="btn btn-primary"
          onClick={() => dispatch({ type: 'SET_INPUT_METHOD', method: 'upload' })}
        >
          Upload your GTINs
        </button>
        <button className="btn" onClick={handleSample}>
          Try with sample data
        </button>
      </div>

      {state.inputMethod === 'upload' && (
        <>
          <div
            className={`${styles.dropzone} ${dragOver ? styles.dragOver : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileRef.current?.click()}
          >
            <strong>Drop a CSV or Excel file here, or click to browse</strong>
            <p>Accepts .csv, .xlsx, .xls (max 10 MB)</p>
            <input
              ref={fileRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              style={{ display: 'none' }}
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) handleFile(file)
              }}
            />
          </div>

          <details className={styles.pasteSection}>
            <summary>Or paste GTINs manually</summary>
            <textarea
              value={pasteText}
              onChange={(e) => {
                setPasteText(e.target.value)
                if (pasteError) setPasteError('')
              }}
              placeholder={'614141000012\n614141000029\n614141000036\n...'}
            />
            {pasteError && <p className="text-error" style={{ margin: '0.25rem 0' }}>{pasteError}</p>}
            <button className="btn btn-primary" onClick={handlePaste}>
              Validate GTINs
            </button>
          </details>
        </>
      )}
    </section>
  )
}
