import Box from '@mui/material/Box'
import FormControl from '@mui/material/FormControl'
import InputAdornment from '@mui/material/InputAdornment'
import InputLabel from '@mui/material/InputLabel'
import MenuItem from '@mui/material/MenuItem'
import Select from '@mui/material/Select'
import TextField from '@mui/material/TextField'
import { draftNeedsAmount } from './alertDraft'
import type { AlertChoice, AlertDraft } from './alertDraft'

interface Props {
  value: AlertDraft
  onChange: (d: AlertDraft) => void
}

/** "Alert me when [the trend changes direction ▾] [5 % / month]". */
export function AlertFields({ value, onChange }: Props) {
  const needsAmount = draftNeedsAmount(value)
  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
      <FormControl size="small" sx={{ minWidth: 200, flex: 2 }}>
        <InputLabel>Alert me when</InputLabel>
        <Select
          value={value.choice}
          label="Alert me when"
          onChange={(e) => onChange({ ...value, choice: e.target.value as AlertChoice })}
        >
          <MenuItem value="trend_flip">the trend changes direction</MenuItem>
          <MenuItem value="slope">the trend crosses a % / month</MenuItem>
          <MenuItem value="above">the value goes above</MenuItem>
          <MenuItem value="below">the value goes below</MenuItem>
          <MenuItem value="none">never (just watch)</MenuItem>
        </Select>
      </FormControl>
      {needsAmount && (
        <TextField
          size="small"
          type="number"
          label={value.choice === 'slope' ? 'Slope' : 'Value'}
          value={value.amount}
          onChange={(e) => onChange({ ...value, amount: e.target.value })}
          placeholder={value.choice === 'slope' ? 'e.g. 5 or -10' : undefined}
          sx={{ flex: 1, minWidth: 110 }}
          slotProps={
            value.choice === 'slope'
              ? { input: { endAdornment: <InputAdornment position="end">% / mo</InputAdornment> } }
              : undefined
          }
        />
      )}
    </Box>
  )
}
