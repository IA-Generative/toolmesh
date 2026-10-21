import { Routes, Route } from "react-router";
import Landing from "./pages/Landing";
import MentionsLegales from "./pages/MentionsLegales";
import RequireAuth from "./auth/RequireAuth";
import Home from "./pages/Home";
import NotFound from "./pages/NotFound";
import PublicLayout from "./layouts/PublicLayout";
import AppLayout from "./layouts/AppLayout";

export default function App() {
  return (
    <>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Landing />}/>
          <Route path="/mentions-legales" element={<MentionsLegales />}/>
          <Route path="*" element={<NotFound />}/>
        </Route>

        <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
          <Route path="/accueil" element={<Home />}/>
        </Route>
      </Routes>
    </>
  );
}
