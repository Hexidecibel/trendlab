import Box from '@mui/material/Box'
import Chip from '@mui/material/Chip'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import type { ReactNode } from 'react'
import { SMOOTHING_PRESETS, formatSlope, isSmoothingPreset } from '../smoothing'
import type { SmoothingPreset } from '../smoothing'

interface Props {
  value: SmoothingPreset
  onChange: (preset: SmoothingPreset) => void
  /** Slope of the fitted line; shown as a chip when the Line preset is on. */
  slopePctPerMonth?: number | null
  /** Extra content on the right of the row. */
  children?: ReactNode
}

export function SmoothingControl({ value, onChange, slopePctPerMonth, children }: Props) {
  const slope = value === 'line' ? formatSlope(slopePctPerMonth) : null
  return (
    <Box
      sx={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'center',
        gap: 1,
        mb: 1,
      }}
    >
      <ToggleButtonGroup
        size="small"
        exclusive
        value={value}
        onChange={(_, v) => {
          if (isSmoothingPreset(v)) onChange(v)
        }}
        aria-label="Smoothing"
        sx={{
          '& .MuiToggleButton-root': {
            px: { xs: 1, sm: 1.5 },
            py: 0.25,
            textTransform: 'none',
            fontSize: '0.8rem',
            lineHeight: 1.6,
          },
        }}
      >
        {SMOOTHING_PRESETS.map((p) => (
          <ToggleButton key={p.value} value={p.value} title={p.hint}>
            {p.label}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
      {slope && (
        <Chip
          size="small"
          color={
            Math.abs(slopePctPerMonth!) < 2 ? 'default' : slopePctPerMonth! > 0 ? 'success' : 'error'
          }
          variant="outlined"
          label={`Line: ${slope} overall`}
          title="Slope of the best-fit line across the whole chart"
          data-testid="slope-chip"
        />
      )}
      {children}
    </Box>
  )
}
