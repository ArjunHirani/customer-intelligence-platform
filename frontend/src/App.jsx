import { useState } from 'react'
import Overview from './components/Overview'
import Segments from './components/Segments'
import ChurnRisk from './components/ChurnRisk'
import Alerts from './components/Alerts'
import WhatIf from './components/WhatIf'

const TABS = [
  { id: 'overview',  label: '📊 Overview' },
  { id: 'segments',  label: '🧩 Segments' },
  { id: 'churn',     label: '⚠️ Churn Risk' },
  { id: 'alerts',    label: '🔔 Alerts' },
  { id: 'whatif',    label: '🎯 What-If' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-indigo-400">
              CustomerIQ
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              AI-Powered Customer Intelligence Platform
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-xs text-slate-400">Live</span>
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-slate-800 border-b border-slate-700 px-6">
        <div className="max-w-7xl mx-auto flex gap-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-indigo-500 text-indigo-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-6">
        {activeTab === 'overview' && <Overview />}
        {activeTab === 'segments' && <Segments />}
        {activeTab === 'churn'    && <ChurnRisk />}
        {activeTab === 'alerts'   && <Alerts />}
        {activeTab === 'whatif'   && <WhatIf />}
      </main>
    </div>
  )
}