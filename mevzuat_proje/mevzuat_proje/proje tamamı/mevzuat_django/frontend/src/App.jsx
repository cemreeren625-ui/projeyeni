import { Routes, Route, Navigate } from "react-router-dom";
import CompaniesList from "./pages/CompaniesList.jsx";
import CompanyDetail from "./pages/CompanyDetail.jsx";

export default function App() {
  return (
    <Routes>
      {/* Ana sayfa -> /companies */}
      <Route path="/" element={<Navigate to="/companies" replace />} />

      {/* Liste */}
      <Route path="/companies" element={<CompaniesList />} />

      {/* Detay */}
      <Route path="/companies/:id" element={<CompanyDetail />} />

      {/* 404 */}
      <Route path="*" element={<div style={{ padding: 24 }}>404</div>} />
    </Routes>
  );
}

