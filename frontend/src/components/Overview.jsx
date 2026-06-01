import { useEffect, useState } from 'react'
import { getOverview, getRevenueTrend, getTopCustomers } from '../api/client'
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, BarChart, Bar
} from 'recharts'

function KPICard({ label, value, sub, color = 'indigo' }) {
  const colors = {
    indigo: 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400',
    emerald: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    amber:   'bg-amber-500/10  border-amber-500/30  text-amber-400',
    rose:    'bg-rose-500/10   border-rose-500/30   text-rose-400',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color]}`}>
      <p className="text-xs text-slate-400 mb-1">{label}</p>
      <p className="text-2xl font-bold text-slate-100">{value}</p>
      {sub && <p className="text-xs mt-1 opacity-70">{sub}</p>}
    </div>
  )
}

export default function Overview() {
  const [kpis, setKpis]   = useState(null)
  const [trend, setTrend] = useState([])
  const [top, setTop]     = useState([])

  useEffect(() => {
    getOverview().then(r => setKpis(r.data))
    getRevenueTrend().then(r => {
      const data = r.data.map(d => ({
        month: d.month?.slice(0, 7),
        revenue: Math.round(d.revenue),
        customers: d.unique_customers,
      }))
      setTrend(data)
    })
    getTopCustomers(8).then(r => setTop(r.data))
  }, [])

  if (!kpis) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-slate-400 animate-pulse">Loading...</div>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* KPI Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Total Customers"
          value={kpis.total_customers?.toLocaleString()}
          color="indigo"
        />
        <KPICard
          label="Total Revenue"
          value={`£${(kpis.total_revenue/1e6).toFixed(2)}M`}
          color="emerald"
        />
        <KPICard
          label="Avg 12M CLV"
          value={`£${kpis.avg_clv?.toLocaleString()}`}
          color="amber"
        />
        <KPICard
          label="Active Alerts"
          value={kpis.active_alerts}
          sub={`${kpis.high_risk_customers} high risk customers`}
          color="rose"
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <KPICard
          label="Champions"
          value={kpis.champions_count?.toLocaleString()}
          sub="Top-tier customers"
          color="emerald"
        />
        <KPICard
          label="Cannot Lose"
          value={kpis.cannot_lose_count}
          sub="Urgent attention needed"
          color="rose"
        />
        <KPICard
          label="Avg Churn Score"
          value={`${(kpis.avg_churn_score * 100).toFixed(1)}%`}
          sub="Across all customers"
          color="amber"
        />
        <KPICard
          label="High Risk"
          value={kpis.high_risk_customers}
          sub="Churn score ≥ 65%"
          color="rose"
        />
      </div>

      {/* Revenue Trend */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">
          Monthly Revenue Trend
        </h2>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={trend}>
            <defs>
              <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
            <XAxis dataKey="month" tick={{fill:'#94a3b8', fontSize:11}} />
            <YAxis tick={{fill:'#94a3b8', fontSize:11}}
                   tickFormatter={v => `£${(v/1000).toFixed(0)}k`}/>
            <Tooltip
              contentStyle={{background:'#1e293b', border:'1px solid #334155', borderRadius:'8px'}}
              formatter={v => [`£${v.toLocaleString()}`, 'Revenue']}
            />
            <Area type="monotone" dataKey="revenue"
              stroke="#6366f1" fill="url(#revGrad)" strokeWidth={2}/>
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Top Customers */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">
          Top Customers by Revenue
        </h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={top} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b"/>
            <XAxis type="number" tick={{fill:'#94a3b8', fontSize:11}}
                   tickFormatter={v => `£${(v/1000).toFixed(0)}k`}/>
            <YAxis dataKey="customer_id" type="category"
                   tick={{fill:'#94a3b8', fontSize:11}} width={70}/>
            <Tooltip
              contentStyle={{background:'#1e293b', border:'1px solid #334155', borderRadius:'8px'}}
              formatter={v => [`£${v.toLocaleString()}`, 'Revenue']}
            />
            <Bar dataKey="total_revenue" fill="#6366f1" radius={[0,4,4,0]}/>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}