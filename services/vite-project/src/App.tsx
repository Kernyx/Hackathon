import { BrowserRouter, Routes, Route } from "react-router-dom"
import Layout from "./components/Layout"
import DashboardPage from "./components/pages/DashboardPage"
import UsersPage from "./components/pages/UsersPage"
import { ThemeProvider } from "./components/theme-provider"
import { ScrollArea } from "@/components/ui/scroll-area"

export default function App() {

  return (

    <BrowserRouter>
      <ThemeProvider defaultTheme="dark" storageKey="vite-ui-theme">
        <ScrollArea className="h-screen w-screen">
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="users" element={<UsersPage />} />
            </Route>

          </Routes>
        </ScrollArea>
      </ThemeProvider>

    </BrowserRouter>

  )

}