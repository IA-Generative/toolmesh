import { Routes, Route } from "react-router";
import AppHeader from "./components/AppHeader";
import AppFooter from "./components/AppFooter";
import Landing from "./pages/Landing";
import MentionsLegales from "./pages/MentionsLegales";

export default function App() {
  return (
    <>
      <AppHeader />
      <Routes>
        <Route path="/" element={<Landing />}/>
        <Route path="/mentions-legales" element={<MentionsLegales />}/>
        <Route path="*" element={<div><br /> <p className="fr-container">Erreur : Page introuvable</p></div>} />
      </Routes>
      <AppFooter />
    </>
  );
}
