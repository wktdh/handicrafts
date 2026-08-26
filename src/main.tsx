import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/lato/400.css'
import '@fontsource/lato/700.css'
import './styles.css'
import './publish.css'
import './auth.css'
import App from './App'

createRoot(document.getElementById('root')!).render(
  <StrictMode><App /></StrictMode>,
)
