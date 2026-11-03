import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import { AuthGate } from '@/features/auth/AuthGate'
import { ToastProvider } from '@/components/ui/Toast'
import App from './App'
import './index.css'

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false, staleTime: 15_000 } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthGate>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthGate>
      </ToastProvider>
    </QueryClientProvider>
  </StrictMode>,
)
