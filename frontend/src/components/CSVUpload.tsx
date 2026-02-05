import { useState, useCallback } from 'react'
import Box from '@mui/material/Box'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import DialogActions from '@mui/material/DialogActions'
import DialogContent from '@mui/material/DialogContent'
import DialogTitle from '@mui/material/DialogTitle'
import TextField from '@mui/material/TextField'
import Typography from '@mui/material/Typography'
import Alert from '@mui/material/Alert'
import CircularProgress from '@mui/material/CircularProgress'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import UploadFileIcon from '@mui/icons-material/UploadFile'

interface Props {
  onUploadComplete?: (uploadId: string, name: string) => void
}

export function CSVUpload({ onUploadComplete }: Props) {
  const [open, setOpen] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState('')
  const [preview, setPreview] = useState<string[][] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const handleOpen = () => {
    setOpen(true)
    setFile(null)
    setName('')
    setPreview(null)
    setError(null)
  }

  const handleClose = () => {
    setOpen(false)
  }

  const parsePreview = useCallback((content: string) => {
    const lines = content.split('\n').slice(0, 6) // Header + 5 rows
    const rows = lines.map(line => {
      // Simple CSV parsing (doesn't handle quoted commas)
      return line.split(',').map(cell => cell.trim())
    }).filter(row => row.some(cell => cell.length > 0))
    setPreview(rows)
  }, [])

  const handleFileSelect = useCallback((selectedFile: File) => {
    if (!selectedFile.name.endsWith('.csv')) {
      setError('Please select a CSV file')
      return
    }
    setFile(selectedFile)
    setError(null)

    // Auto-set name from filename
    const baseName = selectedFile.name.replace(/\.csv$/i, '')
    setName(baseName)

    // Read preview
    const reader = new FileReader()
    reader.onload = (e) => {
      const content = e.target?.result as string
      parsePreview(content)
    }
    reader.readAsText(selectedFile)
  }, [parsePreview])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const droppedFile = e.dataTransfer.files[0]
    if (droppedFile) {
      handleFileSelect(droppedFile)
    }
  }, [handleFileSelect])

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(true)
  }

  const handleDragLeave = () => {
    setDragOver(false)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0]
    if (selectedFile) {
      handleFileSelect(selectedFile)
    }
  }

  const handleUpload = async () => {
    if (!file || !name.trim()) return

    setLoading(true)
    setError(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('name', name.trim())

    try {
      const response = await fetch('/api/upload-csv', {
        method: 'POST',
        body: formData,
      })

      if (!response.ok) {
        const detail = await response.json().catch(() => ({ detail: response.statusText }))
        throw new Error(detail.detail || `Upload failed: ${response.status}`)
      }

      const result = await response.json()
      onUploadComplete?.(result.upload_id, result.name)
      handleClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Button
        variant="outlined"
        size="small"
        startIcon={<UploadFileIcon />}
        onClick={handleOpen}
        sx={{ textTransform: 'none' }}
      >
        Upload CSV
      </Button>

      <Dialog open={open} onClose={handleClose} maxWidth="md" fullWidth>
        <DialogTitle>Upload CSV Data</DialogTitle>
        <DialogContent>
          {error && (
            <Alert severity="error" sx={{ mb: 2 }}>
              {error}
            </Alert>
          )}

          <Box
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            sx={{
              border: '2px dashed',
              borderColor: dragOver ? 'primary.main' : 'grey.400',
              borderRadius: 2,
              p: 4,
              textAlign: 'center',
              bgcolor: dragOver ? 'action.hover' : 'background.paper',
              cursor: 'pointer',
              transition: 'all 0.2s',
              mb: 2,
            }}
            onClick={() => document.getElementById('csv-file-input')?.click()}
          >
            <input
              id="csv-file-input"
              type="file"
              accept=".csv"
              onChange={handleInputChange}
              style={{ display: 'none' }}
            />
            <UploadFileIcon sx={{ fontSize: 48, color: 'grey.500', mb: 1 }} />
            <Typography variant="body1" gutterBottom>
              {file ? file.name : 'Drop CSV file here or click to select'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              File should have date and value columns
            </Typography>
          </Box>

          <TextField
            label="Dataset Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            fullWidth
            size="small"
            sx={{ mb: 2 }}
            placeholder="e.g., Sales Data 2024"
          />

          {preview && preview.length > 0 && (
            <Box>
              <Typography variant="subtitle2" gutterBottom>
                Preview (first 5 rows):
              </Typography>
              <Box sx={{ overflow: 'auto', maxHeight: 200 }}>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      {preview[0].map((cell, i) => (
                        <TableCell key={i} sx={{ fontWeight: 'bold' }}>
                          {cell}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {preview.slice(1).map((row, rowIdx) => (
                      <TableRow key={rowIdx}>
                        {row.map((cell, cellIdx) => (
                          <TableCell key={cellIdx}>{cell}</TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Box>
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} disabled={loading}>
            Cancel
          </Button>
          <Button
            onClick={handleUpload}
            variant="contained"
            disabled={!file || !name.trim() || loading}
            startIcon={loading ? <CircularProgress size={16} /> : undefined}
          >
            {loading ? 'Uploading...' : 'Upload'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}
