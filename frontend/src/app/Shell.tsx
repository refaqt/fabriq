import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Job, type Workspace } from "./api";
import { useFabriqEvents } from "./events";
import { JobDrawer } from "../modules/doqs/JobDrawer";

const LOGO = "https://www.refaqt.com/assets/refaqt-logo-BYNUon1n.png";

export function Shell({ children }: { children: ReactNode }) {
  const workspace = useQuery({ queryKey: ["workspace"], queryFn: () => api.get<Workspace>("/api/workspace") });
  const jobs = useQuery({ queryKey: ["jobs"], queryFn: () => api.get<Job[]>("/api/jobs"), refetchInterval: 5000 });
  const [drawerOpen, setDrawerOpen] = useState(false);
  useFabriqEvents((job) => {
    const j = job as Job;
    if (j.state === "running" || j.state === "failed") setDrawerOpen(true);
  });
  const running = (jobs.data ?? []).filter((j) => j.state === "running" || j.state === "queued").length;
  const nav = workspace.data?.modules.flatMap((m) => m.nav) ?? [];

  return (
    <div className="flex h-full">
      <aside className="flex w-56 shrink-0 flex-col border-r bg-card/60 p-4">
        <div className="mb-6 flex items-center gap-2">
          <img src={LOGO} alt="Refaqt" className="h-6" />
          <span className="text-sm font-semibold tracking-wide text-muted-foreground">fabriq</span>
        </div>
        <nav className="flex flex-col gap-1">
          {nav.map((item) => (
            <NavLink key={item.path} to={item.path} end={item.path === "/"}
              className={({ isActive }) => `rounded-[var(--radius)] px-3 py-2 text-sm ${isActive ? "bg-primary/20 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto text-xs text-muted-foreground">
          <div className="truncate" title={workspace.data?.root}>{workspace.data?.name ?? "…"}</div>
          <div>{workspace.data ? `doqs ${workspace.data.doqs.ok ? "ok" : "not loaded"} · fabriq ${workspace.data.fabriq}` : ""}</div>
        </div>
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto p-6">
        {workspace.data && !workspace.data.doqs.ok && (
          <div className="mb-4 rounded-[var(--radius)] border border-destructive/50 bg-destructive/10 p-3 text-sm">{workspace.data.doqs.error}</div>
        )}
        {children}
      </main>
      <button onClick={() => setDrawerOpen((o) => !o)}
        className="fixed bottom-4 right-4 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg">
        Jobs{running ? ` · ${running} running` : ""}
      </button>
      {drawerOpen && <JobDrawer jobs={jobs.data ?? []} onClose={() => setDrawerOpen(false)} />}
    </div>
  );
}
