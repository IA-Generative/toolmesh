import { Outlet } from "react-router";
import AppHeader from "../components/AppHeader";
import AppFooter from "../components/AppFooter";

export default function PublicLayout(){
    return(
        <>
            <AppHeader />
            <Outlet />
            <AppFooter />
        </>
    )
}