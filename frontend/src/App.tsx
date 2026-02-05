import { ThemeProvider, createTheme, CssBaseline } from '@mui/material'
import AppBar from '@mui/material/AppBar'
import Container from '@mui/material/Container'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import { Dashboard } from './components/Dashboard'

const theme = createTheme({
  palette: {
    primary: { main: '#3b82f6' },
    secondary: { main: '#f97316' },
    background: { default: '#f8fafc' },
  },
  typography: {
    fontFamily: '"Inter", "Roboto", "Helvetica", "Arial", sans-serif',
  },
})

export default function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static" color="default" elevation={1}>
        <Toolbar>
          <div>
            <Typography variant="h6" fontWeight={700}>
              TrendLab
            </Typography>
            <Typography variant="caption" color="text.secondary">
              AI-powered trend analysis and forecasting
            </Typography>
          </div>
        </Toolbar>
      </AppBar>
      <Container maxWidth="xl" sx={{ py: 3 }}>
        <Dashboard />
      </Container>
    </ThemeProvider>
  )
}
