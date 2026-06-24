import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { fetchMe, login as loginRequest, register as registerRequest } from "@/api/auth";
import { Spinner } from "@/components/ui";
import { APP_NAME } from "@/lib/config";
import { useAuthStore } from "@/store/authStore";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const setUser = useAuthStore((s) => s.setUser);

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("admin@ai-autocontour.dev");
  const [password, setPassword] = useState("admin12345");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      if (mode === "register") {
        await registerRequest(email, password, fullName);
      }
      const tokens = await loginRequest(email, password);
      login(tokens.access_token, tokens.refresh_token);
      const me = await fetchMe();
      setUser(me);
      navigate("/");
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-gradient-to-br from-surface-950 via-surface-900 to-surface-950 p-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-brand-400 to-accent text-xl font-bold text-white">
            L
          </div>
          <h1 className="text-2xl font-bold text-white">{APP_NAME}</h1>
          <p className="text-sm text-slate-400">AI-Powered Medical Imaging Platform</p>
        </div>

        <form onSubmit={onSubmit} className="panel space-y-4 p-6">
          <div className="flex rounded-md bg-surface-900 p-1 text-sm">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 rounded px-3 py-1.5 capitalize transition-colors ${
                  mode === m ? "bg-brand-600 text-white" : "text-slate-400"
                }`}
              >
                {m}
              </button>
            ))}
          </div>

          {mode === "register" && (
            <div>
              <label className="mb-1 block text-xs text-slate-400">Full name</label>
              <input
                className="input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Dr. Jane Doe"
              />
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs text-slate-400">Email</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-xs text-slate-400">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && <p className="text-sm text-red-400">{error}</p>}

          <button type="submit" className="btn-primary w-full" disabled={loading}>
            {loading && <Spinner />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>

          <p className="text-center text-[11px] text-slate-500">
            Demo: admin@ai-autocontour.dev / admin12345
          </p>
        </form>
      </div>
    </div>
  );
}
