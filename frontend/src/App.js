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
                background: '#18181b',
                border: '1px solid #27272a',
                color: '#fafafa',
                fontFamily: "'IBM Plex Sans', sans-serif",
                borderRadius: '0px',
              },
            }}
          />
          <main className="flex-1">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/academy" element={<Academy />} />
              <Route path="/marketplace" element={<Marketplace />} />
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
