import { Dashboard } from './components/Dashboard'

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">TrendLab</h1>
        <p className="text-sm text-gray-500">
          AI-powered trend analysis and forecasting
        </p>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-6">
        <Dashboard />
      </main>
    </div>
  )
}
