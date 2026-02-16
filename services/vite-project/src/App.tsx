import { BrowserRouter, Routes, Route } from "react-router-dom"
import Layout from "./components/Layout"
import DashboardPage from "./components/pages/DashboardPage"
import UsersPage from "./components/pages/UsersPage"
import { ScrollArea } from "@/components/ui/scroll-area"
import AuthForm from "./components/pages/AuthForm/AuthForm"

export default function App() {

  return (

    <BrowserRouter>
        <ScrollArea className="h-screen w-screen">
          <Routes>
            <Route path="/login" element={<AuthForm />} />
            <Route path="/signup" element={<AuthForm />} />

            <Route path="/" element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="users" element={<UsersPage />} />
            </Route>

          </Routes>
        </ScrollArea>
    </BrowserRouter>

  )

}