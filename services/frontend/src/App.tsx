import './App.css'
import AuthForm from "./components/AuthForm"

function App() {
  return (
    <div data-theme="dark" className="flex items-center justify-center bg-[#1A1A1A]">
      <div className="absolute inset-0 bg-cover bg-blue-500/20 blur-[100px] s-64 m-auto rounded-full" />
      <div className="relative z-10">
        <AuthForm />
      </div>
    </div>
  )
}

export default App
