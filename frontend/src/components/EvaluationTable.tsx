import { useState } from 'react'
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

  const arrow = (key: SortKey) =>
    sortKey === key ? (sortAsc ? ' \u2191' : ' \u2193') : ''

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-3">
        Model Comparison
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-200">
              <th
                className="text-left py-2 px-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort('model_name')}
              >
                Model{arrow('model_name')}
              </th>
              <th
                className="text-right py-2 px-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort('mae')}
              >
                MAE{arrow('mae')}
              </th>
              <th
                className="text-right py-2 px-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort('rmse')}
              >
                RMSE{arrow('rmse')}
              </th>
              <th
                className="text-right py-2 px-2 cursor-pointer hover:text-blue-600"
                onClick={() => handleSort('mape')}
              >
                MAPE %{arrow('mape')}
              </th>
              <th className="text-right py-2 px-2">Train</th>
              <th className="text-right py-2 px-2">Test</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((ev) => (
              <tr
                key={ev.model_name}
                className={
                  ev.model_name === recommended
                    ? 'bg-blue-50 font-semibold'
                    : 'hover:bg-gray-50'
                }
              >
                <td className="py-1.5 px-2">
                  {ev.model_name}
                  {ev.model_name === recommended && (
                    <span className="ml-1 text-blue-600 text-[10px]">
                      BEST
                    </span>
                  )}
                </td>
                <td className="text-right py-1.5 px-2">
                  {ev.mae.toFixed(2)}
                </td>
                <td className="text-right py-1.5 px-2">
                  {ev.rmse.toFixed(2)}
                </td>
                <td className="text-right py-1.5 px-2">
                  {ev.mape.toFixed(1)}
                </td>
                <td className="text-right py-1.5 px-2">{ev.train_size}</td>
                <td className="text-right py-1.5 px-2">{ev.test_size}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
