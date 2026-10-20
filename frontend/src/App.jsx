import { Routes, Route } from "react-router";
import AppHeader from "./components/AppHeader";
import AppFooter from "./components/AppFooter";
import Landing from "./pages/Landing";
import MentionsLegales from "./pages/MentionsLegales";
import RequireAuth from "./auth/RequireAuth";
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";

export default function App() {
  return (
    <>
      <AppHeader />
      <Routes>
        <Route path="/" element={<Landing />}/>
        <Route path="/mentions-legales" element={<MentionsLegales />}/>
        <Route path="/accueil" element={<RequireAuth><Home /></RequireAuth>} />
        <Route path="*" element={<NotFound />} />
      </Routes>
      <AppFooter />
    </>
  );
}
