import { useEffect, useState } from 'react'
import { getAlerts, resolveAlert } from '../api/client'

const SEVERITY_STYLES = {
  high:   'bg-rose-500/20   text-rose-400   border-rose-500/40',
  medium: 'bg-amber-500/20  text-amber-400  border-amber-500/40',
  low:    'bg-slate-500/20  text-slate-400  border-slate-500/40',
}

export default function Alerts() {
  const [alerts, setAlerts] = useState([])

  const fetchAlerts = () =>
    getAlerts().then(r => setAlerts(r.data))

  useEffect(() => { fetchAlerts() }, [])

  const handleResolve = (id) => {
    resolveAlert(id).then(fetchAlerts)
  }

  const high   = alerts.filter(a => a.severity === 'high')
  const medium = alerts.filter(a => a.severity === 'medium')
  const low    = alerts.filter(a => a.severity === 'low')

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-rose-400">{high.length}</p>
          <p className="text-xs text-slate-400 mt-1">High severity</p>
        </div>
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-amber-400">{medium.length}</p>
          <p className="text-xs text-slate-400 mt-1">Medium severity</p>
        </div>
        <div className="bg-slate-700/50 border border-slate-600 rounded-xl p-4 text-center">
          <p className="text-3xl font-bold text-slate-300">{low.length}</p>
          <p className="text-xs text-slate-400 mt-1">Low severity</p>
        </div>
      </div>

      <div className="space-y-3">
        {alerts.length === 0 && (
          <div className="text-center text-slate-500 py-12">No active alerts</div>
        )}
        {alerts.map(alert => (
          <div
            key={alert.alert_id}
            className={`rounded-xl border p-4 ${SEVERITY_STYLES[alert.severity]}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full border
                    ${SEVERITY_STYLES[alert.severity]}`}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <span className="text-xs text-slate-500">{alert.alert_type}</span>
                </div>
                <p className="text-sm text-slate-200">{alert.description}</p>
                {alert.metric_name && (
                  <p className="text-xs text-slate-500 mt-1">
                    {alert.metric_name}: {alert.metric_value?.toFixed(2)}
                    {alert.baseline_value != null &&
                      ` (baseline: ${alert.baseline_value.toFixed(2)})`}
                  </p>
                )}
                <p className="text-xs text-slate-600 mt-1">
                  {new Date(alert.detected_at).toLocaleString()}
                </p>
              </div>
              <button
                onClick={() => handleResolve(alert.alert_id)}
                className="shrink-0 text-xs px-3 py-1.5 bg-slate-700 hover:bg-slate-600
                  text-slate-300 rounded-lg transition-colors border border-slate-600"
              >
                Resolve
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}