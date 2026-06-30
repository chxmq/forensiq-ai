import { BrowserRouter, Routes, Route } from "react-router-dom";
import AuthGate from "./components/AuthGate";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Applications from "./pages/Applications";
import ApplicationDetail from "./pages/ApplicationDetail";
import NewApplication from "./pages/NewApplication";
import Cases from "./pages/Cases";
import Settings from "./pages/Settings";
import Login from "./pages/Login";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<AuthGate />}>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="applications" element={<Applications />} />
            <Route path="applications/:id" element={<ApplicationDetail />} />
            <Route path="new" element={<NewApplication />} />
            <Route path="cases" element={<Cases />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
