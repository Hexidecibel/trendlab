import Box from '@mui/material/Box'
import ToggleButton from '@mui/material/ToggleButton'
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup'
import Typography from '@mui/material/Typography'
import type { ForecastComparison } from '../api/types'

interface Props {
  forecast: ForecastComparison
  selected: string
  onChange: (model: string) => void
}

export function ModelSelector({ forecast, selected, onChange }: Props) {
  const evalMap = new Map(
    forecast.evaluations.map((e) => [e.model_name, e]),
  )

  return (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
      <Typography variant="body2" fontWeight={500}>
        Model:
      </Typography>
      <ToggleButtonGroup
        size="small"
        exclusive
        value={selected}
        onChange={(_e, val) => { if (val) onChange(val) }}
      >
        {forecast.forecasts.map((f) => {
          const isRecommended = f.model_name === forecast.recommended_model
          const ev = evalMap.get(f.model_name)
          return (
            <ToggleButton
              key={f.model_name}
              value={f.model_name}
              sx={{ textTransform: 'none', fontSize: '0.75rem', px: 1.5 }}
            >
              {f.model_name}
              {isRecommended && ' *'}
              {ev && ` (MAE: ${ev.mae.toFixed(2)})`}
            </ToggleButton>
          )
        })}
      </ToggleButtonGroup>
    </Box>
  )
}
