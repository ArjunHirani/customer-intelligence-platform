import { useState } from 'react'
import { runWhatIf } from '../api/client'

const SEGMENTS = [
  'Champions', 'Loyal Customers', 'Potential Loyalists',
  'Recent Customers', 'Promising', 'At Risk',
  'Cannot Lose Them', 'Hibernating'
]

export default function WhatIf() {
  const [segment, setSegment]       = useState('At Risk')
  const [discount, setDiscount]     = useState(15)
  const [nCustomers, setNCustomers] = useState(50)
  const [result, setResult]         = useState(null)
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState(null)

  const simulate = () => {
    setLoading(true)
    setError(null)
    runWhatIf({ segment, discount_pct: discount, n_customers: nCustomers })
      .then(r => setResult(r.data))
      .catch(() => setError('Simulation failed. Try a different segment.'))
      .finally(() => setLoading(false))
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-6">
        <h2 className="text-sm font-semibold text-slate-300 mb-1">
          Revenue Recovery Simulator
        </h2>
        <p className="text-xs text-slate-500 mb-6">
          Model the ROI of a targeted discount campaign before you run it
        </p>

        <div className="space-y-5">
          {/* Segment */}
          <div>
            <label className="block text-xs text-slate-400 mb-1.5">Target segment</label>
            <select
              value={segment}
              onChange={e => setSegment(e.target.value)}
              className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2.5
                text-sm text-slate-200 outline-none focus:border-indigo-500"
            >
              {SEGMENTS.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>

          {/* Discount */}
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <label className="text-slate-400">Discount offered</label>
              <span className="font-bold text-indigo-400">{discount}%</span>
            </div>
            <input
              type="range" min={5} max={50} value={discount}
              onChange={e => setDiscount(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <div className="flex justify-between text-xs text-slate-600 mt-0.5">
              <span>5%</span><span>50%</span>
            </div>
          </div>

          {/* N customers */}
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <label className="text-slate-400">Customers to target</label>
              <span className="font-bold text-indigo-400">{nCustomers}</span>
            </div>
            <input
              type="range" min={5} max={200} value={nCustomers}
              onChange={e => setNCustomers(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
          </div>

          <button
            onClick={simulate}
            disabled={loading}
            className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50
              text-white font-semibold py-2.5 rounded-lg transition-colors text-sm"
          >
            {loading ? 'Simulating...' : 'Run Simulation →'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-400 text-sm">
          {error}
        </div>
      )}

      {result && (
        <div className="bg-slate-800 rounded-xl border border-slate-700 p-6 space-y-5">
          <h3 className="text-sm font-semibold text-slate-300">Simulation Results</h3>

          <div className="grid grid-cols-2 gap-3">
            {[
              { label: 'Customers targeted',    value: result.customers_targeted,                         color: 'indigo' },
              { label: 'Avg CLV targeted',       value: `£${result.avg_clv_targeted?.toLocaleString()}`,  color: 'blue'   },
              { label: 'Cost of campaign',       value: `£${result.cost_of_intervention?.toLocaleString()}`, color: 'amber'},
              { label: 'Est. revenue saved',     value: `£${result.estimated_revenue_saved?.toLocaleString()}`, color: 'emerald'},
            ].map(item => (
              <div key={item.label} className="bg-slate-900 rounded-lg p-3">
                <p className="text-xs text-slate-500">{item.label}</p>
                <p className="text-xl font-bold text-slate-100 mt-0.5">{item.value}</p>
              </div>
            ))}
          </div>

          {/* ROI meter */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-400">Campaign ROI</span>
              <span className={`font-bold text-lg ${result.roi > 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {result.roi > 0 ? '+' : ''}{result.roi?.toFixed(1)}%
              </span>
            </div>
            <div className="w-full bg-slate-700 rounded-full h-3">
              <div
                className={`h-3 rounded-full ${result.roi > 0 ? 'bg-emerald-500' : 'bg-rose-500'}`}
                style={{ width: `${Math.min(Math.abs(result.roi), 100)}%` }}
              />
            </div>
          </div>

          <div className={`rounded-lg p-4 border text-sm ${
            result.roi > 50  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300' :
            result.roi > 0   ? 'bg-amber-500/10   border-amber-500/30   text-amber-300'   :
                               'bg-rose-500/10    border-rose-500/30    text-rose-300'
          }`}>
            {result.recommendation}
          </div>
        </div>
      )}
    </div>
  )
}