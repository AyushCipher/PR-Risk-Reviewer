import { getMe, loginWithGitHub, loginWithGoogle, logout } from "../api";
import { useEffect, useState } from "react";

export default function UserBadge({ onAuthChange }) {
  const [user, setUser] = useState(undefined); // undefined = loading

  useEffect(() => {
    getMe().then((u) => {
      setUser(u);
      if (onAuthChange) onAuthChange(u);
    });
  }, []);

  async function handleLogout() {
    await logout();
    setUser(null);
    if (onAuthChange) onAuthChange(null);
  }

  // Still loading
  if (user === undefined) return null;

  // Not logged in — Show OAuth Sign-in buttons
  if (!user) {
    return (
      <div className="flex items-center gap-2">
        {/* Sign in with Google */}
        <button
          onClick={loginWithGoogle}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs hover:bg-slate-50 transition"
          title="Sign in with Google"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"
            />
            <path
              fill="#34A853"
              d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.25v3.15C3.26 21.36 7.36 24 12 24z"
            />
            <path
              fill="#FBBC05"
              d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.25C.45 8.18 0 9.97 0 12s.45 3.82 1.25 5.42l4.03-3.15z"
            />
            <path
              fill="#EA4335"
              d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.36 0 3.26 2.64 1.25 6.58l4.03 3.15c.95-2.83 3.6-4.98 6.72-4.98z"
            />
          </svg>
          Google
        </button>

        {/* Sign in with GitHub */}
        <button
          onClick={loginWithGitHub}
          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-xs hover:bg-slate-50 transition"
          title="Sign in with GitHub"
        >
          <svg viewBox="0 0 16 16" className="h-3.5 w-3.5 fill-current" aria-hidden="true">
            <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
          </svg>
          GitHub
        </button>
      </div>
    );
  }

  // Logged in
  return (
    <div className="flex items-center gap-2.5 bg-white border border-slate-200 px-3 py-1.5 rounded-xl shadow-xs">
      {user.avatar_url ? (
        <img
          src={user.avatar_url}
          alt={user.login}
          className="h-6 w-6 rounded-full border border-slate-200"
        />
      ) : (
        <div className="h-6 w-6 rounded-full bg-indigo-100 text-indigo-700 flex items-center justify-center font-bold text-xs">
          {user.login?.charAt(0).toUpperCase()}
        </div>
      )}
      <span className="text-xs text-slate-800 font-semibold">{user.login}</span>
      <button
        onClick={handleLogout}
        className="text-[11px] text-slate-400 hover:text-slate-600 underline ml-1 cursor-pointer"
      >
        Sign out
      </button>
    </div>
  );
}
