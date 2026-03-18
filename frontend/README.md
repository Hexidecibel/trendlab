# TrendLab Frontend

React-based dashboard for the TrendLab trend analysis platform.

## Tech Stack

- **React 19** with TypeScript
- **Vite** for dev server and bundling
- **Material UI (MUI)** for component library
- **Chart.js** with react-chartjs-2 for data visualization

## Project Structure

```
src/
├── api/
│   ├── client.ts        # API client functions (fetch-based)
│   └── types.ts         # TypeScript interfaces matching backend schemas
├── components/
│   ├── Dashboard.tsx     # Main dashboard with tabs (Forecast/Compare/Correlate)
│   ├── QueryForm.tsx     # Data source + query input form
│   ├── CompareForm.tsx   # Multi-series comparison form
│   ├── NaturalQueryInput.tsx  # Natural language search bar
│   ├── AnalysisPanel.tsx # Trend/seasonality/anomaly summary
│   ├── InsightPanel.tsx  # AI-generated commentary (streaming SSE)
│   ├── ErrorAlert.tsx    # Friendly error display with hints
│   ├── charts/
│   │   ├── ForecastChart.tsx  # Time series + forecast overlay
│   │   └── CompareChart.tsx   # Multi-series comparison chart
│   └── ...
├── hooks/
│   └── useApi.ts         # Data-fetching hook for series/analysis/forecast
├── App.tsx               # Root layout with theme
└── main.tsx              # Entry point
```

## Development

```bash
# Install dependencies
npm install

# Start dev server (proxies /api to backend on :8000)
npm run dev

# Type-check without emitting
npx tsc --noEmit

# Build for production
npm run build
```

## API Communication

The frontend communicates with the FastAPI backend via a fetch-based client (`src/api/client.ts`). In development, Vite's proxy forwards `/api` requests to `http://localhost:8000`. In production, the FastAPI server serves the built frontend from `frontend/dist/`.

Error responses from the backend follow a structured format with `detail`, `hint`, `error_code`, and `request_id` fields. The `ApiError` class in the client extracts these for display in the UI.

## Key Components

| Component | Purpose |
|-----------|---------|
| `Dashboard` | Main layout with Forecast / Compare / Correlate tabs |
| `QueryForm` | Source selector, query input, date range, resample options |
| `NaturalQueryInput` | "Ask anything" search bar powered by AI query parsing |
| `ForecastChart` | Chart.js line chart with historical data + forecast bands |
| `CompareChart` | Normalized multi-series overlay chart |
| `AnalysisPanel` | Trend direction, anomalies, seasonality, structural breaks |
| `InsightPanel` | Streaming AI commentary on the data |
| `ErrorAlert` | User-friendly error display with hints and request IDs |
| `CorrelateTab` | Pearson/Spearman correlation with scatter plot |
| `WatchlistPanel` | Track trends and get threshold alerts |
