import { useEffect, useState } from 'react'
import { getSegments } from '../api/client'
import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'

const SEGMENT_COLORS = {
  'Champions':          'bg-emerald-500/20 text-emerald-400 border-emerald-500/40',
  'Loyal Customers':    'bg-indigo-500/20  text-indigo-400  border-indigo-500/40',
  'Potential Loyalists':'bg-blue-500/20    text-blue-400    border-blue-500/40',
  'Recent Customers':   'bg-cyan-500/20    text-cyan-400    border-cyan-500/40',
  'Promising':          'bg-amber-500/20   text-amber-400   border-amber-500/40',
  'At Risk':            'bg-orange-500/20  text-orange-400  border-orange-500/40',
  'Cannot Lose Them':   'bg-rose-500/20    text-rose-400    border-rose-500/40',
  'Hibernating':        'bg-slate-500/20   text-slate-400   border-slate-500/40',
}

export default function Segments() {
  const [segments, setSegments] = useState([])
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    getSegments().then(r => {
      setSegments(r.data)
      setSelected(r.data[0])
    })
  }, [])

  const radarData = selected ? [
    { metric: 'Recency',   value: Math.max(0, 100 - selected.avg_recency / 5) },
    { metric: 'Frequency', value: Math.min(100, selected.avg_frequency * 5) },
    { metric: 'Monetary',  value: Math.min(100, selected.avg_monetary / 200) },
    { metric: 'CLV',       value: Math.min(100, (selected.avg_clv || 0) / 100) },
    { metric: 'Loyalty',   value: Math.max(0, 100 - selected.avg_churn_score * 100) },
  ] : []

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        {segments.map(seg => (
          <button
            key={seg.rfm_segment}
            onClick={() => setSelected(seg)}
            className={`text-left p-4 rounded-xl border transition-all ${
              SEGMENT_COLORS[seg.rfm_segment] || 'bg-slate-700 border-slate-600'
            } ${selected?.rfm_segment === seg.rfm_segment ? 'ring-2 ring-white/20' : ''}`}
          >
            <p className="font-semibold text-sm">{seg.rfm_segment}</p>
            <p className="text-2xl font-bold text-slate-100 mt-1">
              {seg.customer_count.toLocaleString()}
            </p>
            <p className="text-xs opacity-70 mt-1">customers</p>
            <div className="mt-2 pt-2 border-t border-white/10 space-y-0.5">
              <p className="text-xs">Avg revenue: £{seg.avg_monetary?.toLocaleString()}</p>
              <p className="text-xs">Churn risk: {(seg.avg_churn_score * 100).toFixed(1)}%</p>
            </div>
          </button>
        ))}
      </div>

      {selected && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
            <h2 className="text-sm font-semibold text-slate-300 mb-1">
              {selected.rfm_segment} — Segment Profile
            </h2>
            <p className="text-xs text-slate-500 mb-4">Click any segment card to compare</p>
            <ResponsiveContainer width="100%" height={220}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#334155"/>
                <PolarAngleAxis dataKey="metric" tick={{fill:'#94a3b8', fontSize:11}}/>
                <Radar dataKey="value" stroke="#6366f1" fill="#6366f1" fillOpacity={0.3}/>
                <Tooltip
                  contentStyle={{background:'#1e293b', border:'1px solid #334155', borderRadius:'8px'}}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
            <h2 className="text-sm font-semibold text-slate-300 mb-4">
              {selected.rfm_segment} — Key Metrics
            </h2>
            <div className="space-y-3">
              {[
                { label: 'Customers',        value: selected.customer_count.toLocaleString() },
                { label: 'Avg Monetary',     value: `£${selected.avg_monetary?.toLocaleString()}` },
                { label: 'Avg CLV (12M)',    value: `£${selected.avg_clv?.toLocaleString() ?? 'N/A'}` },
                { label: 'Total Revenue',    value: `£${selected.total_revenue?.toLocaleString()}` },
                { label: 'Avg Recency',      value: `${selected.avg_recency} days ago` },
                { label: 'Avg Frequency',    value: `${selected.avg_frequency} orders` },
                { label: 'Avg Churn Score',  value: `${(selected.avg_churn_score * 100).toFixed(1)}%` },
              ].map(item => (
                <div key={item.label} className="flex justify-between items-center
                  py-2 border-b border-slate-700">
                  <span className="text-xs text-slate-400">{item.label}</span>
                  <span className="text-sm font-semibold text-slate-100">{item.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}