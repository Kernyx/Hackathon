import { BrowserRouter, Routes, Route } from "react-router-dom"
import Layout from "./components/Layout"
// Импортируем переименованные компоненты
import AgentPage from "./components/pages/AgentPage"
import AgentRelationPage from "./components/pages/AgentRelationPage"
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
              <Route index element={<AgentPage />} />
              <Route path="relations" element={<AgentRelationPage />} />
            </Route>

          </Routes>
        </ScrollArea>
    </BrowserRouter>
  )
}