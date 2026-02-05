import { useState } from 'react'
import Button from '@mui/material/Button'
import CircularProgress from '@mui/material/CircularProgress'
import PictureAsPdfIcon from '@mui/icons-material/PictureAsPdf'

interface Props {
  source: string
  query: string
  horizon: number
  start?: string
  end?: string
  resample?: string
  apply?: string
}

export function ExportPdfButton({
  source,
  query,
  horizon,
  start,
  end,
  resample,
  apply,
}: Props) {
  const [loading, setLoading] = useState(false)

  const handleExport = async () => {
    setLoading(true)

    try {
      const params = new URLSearchParams({
        source,
        query,
        horizon: String(horizon),
      })
      if (start) params.set('start', start)
      if (end) params.set('end', end)
      if (resample) params.set('resample', resample)
      if (apply) params.set('apply', apply)

      const response = await fetch(`/api/export-pdf?${params}`)

      if (!response.ok) {
        const detail = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(detail.detail || `HTTP ${response.status}`)
      }

      // Get filename from Content-Disposition header or generate one
      const contentDisposition = response.headers.get('Content-Disposition')
      let filename = `trendlab-${source}-${query}.pdf`
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?([^"]+)"?/)
        if (match) filename = match[1]
      }

      // Download the file
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    } catch (err) {
      console.error('PDF export failed:', err)
      // Could add a snackbar/toast here
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button
      variant="outlined"
      size="small"
      startIcon={loading ? <CircularProgress size={16} /> : <PictureAsPdfIcon />}
      onClick={handleExport}
      disabled={loading}
      sx={{ textTransform: 'none' }}
    >
      {loading ? 'Generating...' : 'Export PDF'}
    </Button>
  )
}
