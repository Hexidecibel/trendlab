import { useState } from 'react'
import Card from '@mui/material/Card'
import CardContent from '@mui/material/CardContent'
import Table from '@mui/material/Table'
import TableBody from '@mui/material/TableBody'
import TableCell from '@mui/material/TableCell'
import TableContainer from '@mui/material/TableContainer'
import TableHead from '@mui/material/TableHead'
import TableRow from '@mui/material/TableRow'
import TableSortLabel from '@mui/material/TableSortLabel'
import Typography from '@mui/material/Typography'
import type { ModelEvaluation } from '../api/types'

interface Props {
  evaluations: ModelEvaluation[]
  recommended: string
}

type SortKey = 'model_name' | 'mae' | 'rmse' | 'mape'

export function EvaluationTable({ evaluations, recommended }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('mae')
  const [sortAsc, setSortAsc] = useState(true)

  const sorted = [...evaluations].sort((a, b) => {
    const av = a[sortKey]
    const bv = b[sortKey]
    if (typeof av === 'string' && typeof bv === 'string') {
      return sortAsc ? av.localeCompare(bv) : bv.localeCompare(av)
    }
    return sortAsc
      ? (av as number) - (bv as number)
      : (bv as number) - (av as number)
  })

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc)
    } else {
      setSortKey(key)
      setSortAsc(true)
    }
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle2" gutterBottom>
          Model Comparison
        </Typography>
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>
                  <TableSortLabel
                    active={sortKey === 'model_name'}
                    direction={sortKey === 'model_name' ? (sortAsc ? 'asc' : 'desc') : 'asc'}
                    onClick={() => handleSort('model_name')}
                  >
                    Model
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortKey === 'mae'}
                    direction={sortKey === 'mae' ? (sortAsc ? 'asc' : 'desc') : 'asc'}
                    onClick={() => handleSort('mae')}
                  >
                    MAE
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortKey === 'rmse'}
                    direction={sortKey === 'rmse' ? (sortAsc ? 'asc' : 'desc') : 'asc'}
                    onClick={() => handleSort('rmse')}
                  >
                    RMSE
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">
                  <TableSortLabel
                    active={sortKey === 'mape'}
                    direction={sortKey === 'mape' ? (sortAsc ? 'asc' : 'desc') : 'asc'}
                    onClick={() => handleSort('mape')}
                  >
                    MAPE %
                  </TableSortLabel>
                </TableCell>
                <TableCell align="right">Train</TableCell>
                <TableCell align="right">Test</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {sorted.map((ev) => (
                <TableRow
                  key={ev.model_name}
                  selected={ev.model_name === recommended}
                  hover
                >
                  <TableCell>
                    {ev.model_name}
                    {ev.model_name === recommended && (
                      <Typography
                        component="span"
                        variant="caption"
                        color="primary"
                        sx={{ ml: 0.5, fontWeight: 600 }}
                      >
                        BEST
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">{ev.mae.toFixed(2)}</TableCell>
                  <TableCell align="right">{ev.rmse.toFixed(2)}</TableCell>
                  <TableCell align="right">{ev.mape.toFixed(1)}</TableCell>
                  <TableCell align="right">{ev.train_size}</TableCell>
                  <TableCell align="right">{ev.test_size}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  )
}
