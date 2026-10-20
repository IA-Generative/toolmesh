import { createContext, useContext, useEffect, useState } from "react";
import { fetchMe, loginUrl, logout } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: "loading", user: null });

  useEffect(() => {
    let cancelled = false; // évite les doubles effets du StrictMode
    fetchMe()
      .then((user) => !cancelled && setState({ status: user ? "authenticated" : "anonymous", user }))
      .catch(() => !cancelled && setState({ status: "anonymous", user: null }));
    return () => { cancelled = true; };
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, loginUrl, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext);
