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

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <CityProvider>
          <ToastProvider>
            <App />
          </ToastProvider>
        </CityProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
