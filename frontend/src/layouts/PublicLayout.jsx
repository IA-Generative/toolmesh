import { Outlet } from "react-router";
import AppHeader from "../components/AppHeader";
import AppFooter from "../components/AppFooter";
import "./PublicLayout.css";

export default function PublicLayout(){
    return(
        <div className="public-layout">
            <AppHeader />
            <Outlet />
            <AppFooter />
        </div>
    )
}