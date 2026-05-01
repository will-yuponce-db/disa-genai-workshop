import { NavLink, Route, Routes } from "react-router-dom";
import Home from "./pages/Home";
import Threats from "./pages/Threats";
import Charts from "./pages/Charts";
import Chat from "./components/Chat";

export default function App() {
  return (
    <div className="flex h-full">
      <aside className="w-56 shrink-0 border-r border-slate-800 p-4 space-y-2">
        <h1 className="text-xl font-bold mb-6">DISA CTI</h1>
        <NavTab to="/" label="Home" />
        <NavTab to="/threats" label="Threats" />
        <NavTab to="/charts" label="Charts" />
      </aside>
      <main className="flex-1 overflow-auto p-6">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/threats" element={<Threats />} />
          <Route path="/charts" element={<Charts />} />
        </Routes>
      </main>
      <aside className="w-96 shrink-0 border-l border-slate-800">
        <Chat />
      </aside>
    </div>
  );
}

function NavTab({ to, label }: { to: string; label: string }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `block px-3 py-2 rounded text-sm ${isActive ? "bg-slate-800 text-white" : "text-slate-300 hover:bg-slate-900"}`
      }
    >
      {label}
    </NavLink>
  );
}
