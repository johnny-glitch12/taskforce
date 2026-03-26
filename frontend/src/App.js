import { useState, createContext, useContext } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Academy from "@/pages/Academy";
import Marketplace from "@/pages/Marketplace";
import Studio from "@/pages/Studio";
import CreatorProfile from "@/pages/CreatorProfile";

export const AuthContext = createContext(null);

export function useAuth() {
  return useContext(AuthContext);
}

function ProtectedRoute({ children }) {
  const { isAdmin } = useAuth();
  if (!isAdmin) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [userEmail, setUserEmail] = useState("");

  const login = (email) => {
    if (email === "admin@nova.ai") {
      setIsAdmin(true);
      setUserEmail(email);
      return true;
    }
    return false;
  };

  const logout = () => {
    setIsAdmin(false);
    setUserEmail("");
  };

  return (
    <AuthContext.Provider value={{ isAdmin, userEmail, login, logout }}>
      <BrowserRouter>
        <div className="min-h-screen bg-zinc-950 flex flex-col">
          <Navbar />
          <Toaster
            position="bottom-right"
            toastOptions={{
              style: {
                background: 'rgba(24, 24, 27, 0.9)',
                backdropFilter: 'blur(12px)',
                border: '1px solid rgba(255,255,255,0.08)',
                color: '#fafafa',
                fontFamily: "'IBM Plex Sans', sans-serif",
                borderRadius: '12px',
                fontSize: '13px',
              },
            }}
          />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/academy" element={<Academy />} />
              <Route path="/marketplace" element={<Marketplace />} />
              <Route path="/creator/:id" element={<CreatorProfile />} />
              <Route
                path="/studio"
                element={
                  <ProtectedRoute>
                    <Studio />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </main>
          <Footer />
        </div>
      </BrowserRouter>
    </AuthContext.Provider>
  );
}

export default App;
