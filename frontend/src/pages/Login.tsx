import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Shield, LogIn } from "lucide-react";
import { api, login } from "../lib/api";
import { setAuth } from "../lib/auth";

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("underwriter");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [authRequired, setAuthRequired] = useState(true);

  useEffect(() => {
    api.get("/auth/status").then((r) => {
      setAuthRequired(r.data.auth_enabled);
      if (!r.data.auth_enabled) {
        login("guest", "guest").then((res) => {
          setAuth(res.access_token, res.username);
          navigate("/", { replace: true });
        }).catch(() => {});
      }
    }).catch(() => {});
  }, [navigate]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const res = await login(username, password);
      setAuth(res.access_token, res.username);
      navigate("/", { replace: true });
    } catch {
      setError("Invalid username or password.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-screen place-items-center bg-canvas px-4">
      <div className="card card-pad w-full max-w-md space-y-6">
        <div className="text-center">
          <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl bg-navy-900 text-white">
            <Shield className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-extrabold text-ink">Forensiq AI</h1>
          <p className="mt-1 text-sm text-muted">Underwriter sign-in</p>
        </div>

        {authRequired && (
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="label">Username</label>
              <input className="input mt-1" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </div>
            <div>
              <label className="label">Password</label>
              <input className="input mt-1" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <button type="submit" className="btn-primary w-full" disabled={busy}>
              <LogIn className="h-4 w-4" /> {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
