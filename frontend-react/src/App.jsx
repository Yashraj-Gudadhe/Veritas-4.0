import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import ChatPage from './pages/ChatPage';
import AccountPage from './pages/AccountPage';

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes */}
          <Route
            path="/chat"
            element={<ProtectedRoute><ChatPage /></ProtectedRoute>}
          />
          <Route
            path="/chat/:chatId"
            element={<ProtectedRoute><ChatPage /></ProtectedRoute>}
          />
          <Route
            path="/account"
            element={<ProtectedRoute><AccountPage /></ProtectedRoute>}
          />

          {/* Root redirect */}
          <Route path="/" element={<Navigate to="/chat" replace />} />

          {/* 404 fallback */}
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
