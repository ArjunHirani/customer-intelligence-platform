import { useEffect, useState } from 'react'
import { getCustomers, getCustomerRisk } from '../api/client'

function RiskBadge({ level }) {
  const styles = {
    high:   'bg-rose-500/20 text-rose-400 border border-rose-500/40',
    medium: 'bg-amber-500/20 text-amber-400 border border-amber-500/40',
    low:    'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40',
  }
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${styles[level] || styles.medium}`}>
      {level}
    </span>
  )
}

export default function ChurnRisk() {
  const [customers, setCustomers] = useState([])
  const [selected, setSelected]   = useState(null)
  const [risk, setRisk]           = useState(null)
  const [loading, setLoading]     = useState(false)
  const [search, setSearch]       = useState('')

  useEffect(() => {
    getCustomers({ limit: 100 }).then(r => setCustomers(r.data))
  }, [])

  const selectCustomer = (c) => {
    setSelected(c)
    setRisk(null)
    setLoading(true)
    getCustomerRisk(c.customer_id)
      .then(r => setRisk(r.data))
      .finally(() => setLoading(false))
  }

  const filtered = customers.filter(c =>
    c.customer_id.includes(search) ||
    (c.rfm_segment || '').toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      {/* Left — customer list */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Customer List</h2>
        <input
          type="text"
          placeholder="Search by ID or segment..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2
            text-sm text-slate-200 placeholder-slate-500 mb-3 outline-none
            focus:border-indigo-500"
        />
        <div className="space-y-1 max-h-[500px] overflow-y-auto pr-1">
          {filtered.map(c => (
            <button
              key={c.customer_id}
              onClick={() => selectCustomer(c)}
              className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors
                flex justify-between items-center
                ${selected?.customer_id === c.customer_id
                  ? 'bg-indigo-600/30 border border-indigo-500/50'
                  : 'hover:bg-slate-700 border border-transparent'}`}
            >
              <div>
                <p className="text-sm font-medium text-slate-200">
                  Customer {c.customer_id}
                </p>
                <p className="text-xs text-slate-500">{c.rfm_segment}</p>
              </div>
              <div className="text-right">
                <p className="text-xs font-semibold text-slate-300">
                  £{(c.monetary || 0).toLocaleString()}
                </p>
                <p className="text-xs text-slate-500">
                  {c.churn_score != null
                    ? `${(c.churn_score * 100).toFixed(0)}% churn`
                    : '—'}
                </p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right — risk detail */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4">
        {!selected && (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            Select a customer to see their churn risk analysis
          </div>
        )}
        {loading && (
          <div className="flex items-center justify-center h-full text-slate-400 animate-pulse text-sm">
            Analyzing...
          </div>
        )}
        {risk && !loading && (
          <div className="space-y-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-slate-300">
                  Customer {risk.customer_id}
                </h2>
                <p className="text-xs text-slate-500">{risk.rfm_segment}</p>
              </div>
              <RiskBadge level={risk.churn_risk_level} />
            </div>

            {/* Churn score bar */}
            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Churn probability</span>
                <span className="font-bold text-slate-200">
                  {(risk.churn_score * 100).toFixed(1)}%
                </span>
              </div>
              <div className="w-full bg-slate-700 rounded-full h-3">
                <div
                  className={`h-3 rounded-full transition-all ${
                    risk.churn_score >= 0.65 ? 'bg-rose-500' :
                    risk.churn_score >= 0.45 ? 'bg-amber-500' : 'bg-emerald-500'
                  }`}
                  style={{ width: `${risk.churn_score * 100}%` }}
                />
              </div>
            </div>

            {/* KPIs */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-slate-900 rounded-lg p-3">
                <p className="text-xs text-slate-500">Revenue</p>
                <p className="text-lg font-bold text-slate-100">
                  £{(risk.monetary || 0).toLocaleString()}
                </p>
              </div>
              <div className="bg-slate-900 rounded-lg p-3">
                <p className="text-xs text-slate-500">12M CLV</p>
                <p className="text-lg font-bold text-slate-100">
                  {risk.clv_12m ? `£${risk.clv_12m.toLocaleString()}` : 'N/A'}
                </p>
              </div>
            </div>

            {/* SHAP factors */}
            <div>
              <h3 className="text-xs font-semibold text-slate-400 mb-2 uppercase tracking-wider">
                Top risk factors (SHAP)
              </h3>
              <div className="space-y-2">
                {risk.top_factors.map((f, i) => {
                  const isPositive = f.shap_value > 0
                  const absVal = Math.abs(f.shap_value)
                  const maxVal = Math.abs(risk.top_factors[0].shap_value)
                  const pct = maxVal > 0 ? (absVal / maxVal) * 100 : 0
                  return (
                    <div key={i}>
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-slate-400">{f.feature.replace(/_/g,' ')}</span>
                        <span className={isPositive ? 'text-rose-400' : 'text-emerald-400'}>
                          {isPositive ? '▲' : '▼'} {Math.abs(f.shap_value).toFixed(4)}
                        </span>
                      </div>
                      <div className="w-full bg-slate-700 rounded-full h-1.5">
                        <div
                          className={`h-1.5 rounded-full ${isPositive ? 'bg-rose-500' : 'bg-emerald-500'}`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
              <p className="text-xs text-slate-600 mt-2">
                ▲ increases churn risk · ▼ reduces churn risk
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}