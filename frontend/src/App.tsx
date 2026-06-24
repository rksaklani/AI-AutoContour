import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { fetchMe } from "@/api/auth";
import { Spinner } from "@/components/ui";
import { tokenStore } from "@/lib/apiClient";
import { LoginPage } from "@/features/auth/LoginPage";
import { StudyListPage } from "@/features/studies/StudyListPage";
import { WorkspacePage } from "@/features/viewer/WorkspacePage";
import { useAuthStore } from "@/store/authStore";

function RequireAuth({ children }: { children: JSX.Element }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

export default function App() {
  const setUser = useAuthStore((s) => s.setUser);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [bootstrapping, setBootstrapping] = useState(true);

  useEffect(() => {
    let active = true;
    async function bootstrap() {
      if (tokenStore.getAccess()) {
        try {
          const me = await fetchMe();
          if (active) setUser(me);
        } catch {
          /* interceptor handles refresh/logout */
        }
      }
      if (active) setBootstrapping(false);
    }
    bootstrap();
    return () => {
      active = false;
    };
  }, [setUser]);

  if (bootstrapping) {
    return (
      <div className="flex h-full items-center justify-center bg-surface-950">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={
          <RequireAuth>
            <StudyListPage />
          </RequireAuth>
        }
      />
      <Route
        path="/studies/:studyId"
        element={
          <RequireAuth>
            <WorkspacePage />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
