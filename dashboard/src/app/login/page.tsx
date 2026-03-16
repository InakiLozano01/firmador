"use client";

import { useState } from "react";
import { AlertTriangle, Lock, User, Eye, EyeOff } from "lucide-react";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [shake, setShake] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ username, password }),
      });

      if (res.ok) {
        window.location.assign("/dashboard");
        return;
      } else {
        const data = await res.json();
        setError(data.error ?? "Credenciales inválidas");
        setShake(true);
        setTimeout(() => setShake(false), 400);
      }
    } catch {
      setError("Error de conexión. Verificá tu red e intentá de nuevo.");
      setShake(true);
      setTimeout(() => setShake(false), 400);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden bg-[hsl(222,25%,4%)]">
      {/* Atmospheric background */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <div className="absolute -top-48 -right-48 w-[600px] h-[600px] bg-blue-600/12 rounded-full blur-[120px]" />
        <div className="absolute -bottom-48 -left-48 w-[500px] h-[500px] bg-indigo-600/8 rounded-full blur-[100px]" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 w-[350px] h-[350px] bg-violet-600/5 rounded-full blur-[90px]" />
      </div>

      {/* Noise texture */}
      <div className="absolute inset-0 noise-texture pointer-events-none" aria-hidden="true" />

      {/* Floating dots */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
        {[
          { top: "15%", left: "20%", delay: "0s", size: "2px" },
          { top: "25%", left: "75%", delay: "0.5s", size: "3px" },
          { top: "55%", left: "10%", delay: "1s", size: "2px" },
          { top: "70%", left: "85%", delay: "1.5s", size: "2px" },
          { top: "40%", left: "90%", delay: "0.8s", size: "3px" },
          { top: "80%", left: "30%", delay: "1.2s", size: "2px" },
        ].map((dot, i) => (
          <span
            key={i}
            className="absolute rounded-full bg-white/20 animate-pulse-dot"
            style={{
              top: dot.top,
              left: dot.left,
              width: dot.size,
              height: dot.size,
              animationDelay: dot.delay,
            }}
          />
        ))}
      </div>

      {/* Card */}
      <div className={`w-full max-w-[400px] relative animate-slide-up ${shake ? "animate-shake" : ""}`}>
        <div className="rounded-2xl border border-white/[0.06] bg-white/[0.03] backdrop-blur-2xl p-8 shadow-2xl shadow-black/20">
          {/* Logo */}
          <div className="text-center mb-8">
            <div className="mx-auto mb-4 h-16 w-16 rounded-2xl gradient-accent flex items-center justify-center text-white font-bold text-xl tracking-tight shadow-lg shadow-blue-500/25 hover:scale-105 transition-transform duration-200">
              OD
            </div>
            <h1 className="text-2xl font-bold text-white tracking-tight" style={{ textWrap: "balance" }}>
              Obs Dashboard
            </h1>
            <p className="text-sm text-white/35 mt-2">
              Ingresá tus credenciales para continuar
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="flex items-center gap-2.5 rounded-xl bg-rose-500/8 border border-rose-500/12 text-rose-300 text-sm p-3.5 animate-fade-in" role="alert">
                <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label htmlFor="login-username" className="text-sm font-medium text-white/50">
                Usuario
              </label>
              <div className="relative">
                <User className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" aria-hidden="true" />
                <input
                  id="login-username"
                  name="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoFocus
                  autoComplete="username"
                  spellCheck={false}
                  className="flex h-12 w-full rounded-xl border border-white/[0.06] bg-white/[0.03] pl-11 pr-4 text-sm text-white placeholder:text-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-500/25 transition-all duration-200"
                  placeholder="tu.usuario"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label htmlFor="login-password" className="text-sm font-medium text-white/50">
                Contraseña
              </label>
              <div className="relative">
                <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-white/20" aria-hidden="true" />
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                  className="flex h-12 w-full rounded-xl border border-white/[0.06] bg-white/[0.03] pl-11 pr-11 text-sm text-white placeholder:text-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/30 focus-visible:border-blue-500/25 transition-all duration-200"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 p-1 text-white/25 hover:text-white/50 transition-colors"
                  aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full h-12 rounded-xl gradient-accent text-white font-semibold text-sm shadow-lg shadow-blue-600/20 hover:shadow-blue-600/35 active:scale-[0.97] transition-all duration-200 disabled:opacity-50 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/30"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  Ingresando…
                </span>
              ) : (
                "Ingresar"
              )}
            </button>
          </form>
        </div>

        {/* Footer text */}
        <p className="text-center text-[11px] text-white/15 mt-6">
          Tribunal de Cuentas de Tucumán — Sistema de Firma Digital
        </p>
      </div>
    </div>
  );
}
