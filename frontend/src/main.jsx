import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import "@codegouvfr/react-dsfr/main.css";
import { startReactDsfr } from "@codegouvfr/react-dsfr/spa";
import App from './App.jsx'
import { BrowserRouter } from "react-router";
import { Link } from "./components/RouterLink";
import { AuthProvider } from './auth/AuthContext.jsx';

startReactDsfr({ defaultColorScheme: "system", Link });

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
