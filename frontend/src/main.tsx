import './styles/tokens.css';
import './styles/base.css';
import './styles/admin.css';

import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';

import App from './App';
import { ToastProvider } from './components/Toast';
import { AuthProvider } from './hooks/useAuth';
import { CityProvider } from './hooks/useCity';
import { GameProvider } from './hooks/useGame';
import { SubscriptionsProvider } from './hooks/useSubscriptions';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CityProvider>
          <ToastProvider>
            <SubscriptionsProvider>
              <GameProvider>
                <App />
              </GameProvider>
            </SubscriptionsProvider>
          </ToastProvider>
        </CityProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
