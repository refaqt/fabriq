import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../app/api";
import { Badge, Button, Card, Empty } from "../../ui/components";

type Lock = { path: string; owner?: string; reason?: string; since?: number; locked_at?: string | null };
type RepoLocks = { path: string; mine: Lock[]; theirs: Lock[]; conflicts: { path: string; owner: string | null }[]; warnings: string[] };
export type LockStatus = { enabled: boolean; repos: Record<string, RepoLocks> };

const reasonText: Record<string, string> = {
  unsaved: "unsaved changes in FreeCAD",
  saved: "changed on disk",
  server: "locked before",
};

export function useLocks(fresh = false) {
  return useQuery({
    queryKey: ["git", "locks", fresh],
    queryFn: () => api.get<LockStatus>(`/api/doqs/git/locks${fresh ? "?fresh=true" : ""}`),
    // A fresh read asks the lock server, so it runs less often.
    refetchInterval: fresh ? 60000 : 15000,
  });
}

/** A red warning for every FreeCAD file this person changes while a colleague holds its lock. */
export function LockConflicts() {
  const locks = useLocks();
  const conflicts = Object.entries(locks.data?.repos ?? {}).flatMap(([repo, r]) => r.conflicts.map((c) => ({ repo, ...c })));
  if (!conflicts.length) return null;
  return (
    <div className="rounded-[var(--radius)] border border-destructive bg-destructive/10 p-4 text-sm">
      <p className="font-semibold text-destructive">A colleague is working on a FreeCAD file you changed</p>
      <p className="mb-2">Git cannot merge two versions of a FreeCAD file. Stop, and close the file without saving. Talk to the colleague first.</p>
      <ul>
        {conflicts.map((c) => <li key={`${c.repo}/${c.path}`}><b>{c.repo}</b>: {c.path} — locked by {c.owner ?? "someone else"}</li>)}
      </ul>
    </div>
  );
}

/** Who holds which FreeCAD file, per repository. */
export function LocksCard() {
  const queryClient = useQueryClient();
  const locks = useLocks(true);
  const unlock = useMutation({
    mutationFn: (body: { repo: string; file: string }) => api.post("/api/doqs/git/locks/unlock", body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["git", "locks"] }),
  });
  if (locks.data && !locks.data.enabled) {
    return <Card title="Locked FreeCAD files"><Empty>FreeCAD files are not locked in this workspace.</Empty></Card>;
  }
  const repos = Object.entries(locks.data?.repos ?? {});
  const any = repos.some(([, r]) => r.mine.length || r.theirs.length || r.warnings.length);
  return (
    <Card title="Locked FreeCAD files">
      <p className="mb-3 text-sm text-muted-foreground">fabriq locks a FreeCAD file as soon as you change it, also before you save. Colleagues then cannot change the same file. The lock goes when the pull request merges, or when you throw the change away.</p>
      {!any ? <Empty>No FreeCAD file is locked.</Empty> : repos.map(([name, r]) => (r.mine.length || r.theirs.length || r.warnings.length) ? (
        <div key={name} className="mb-3">
          <h3 className="text-sm font-semibold">{name}</h3>
          <ul className="text-sm">
            {r.mine.map((l) => (
              <li key={l.path} className="flex items-center gap-2">
                <Badge tone="ok">you</Badge><span>{l.path}</span>
                <span className="text-xs text-muted-foreground">{reasonText[l.reason ?? ""] ?? l.reason}</span>
                <Button kind="ghost" disabled={unlock.isPending} onClick={() => unlock.mutate({ repo: name, file: l.path })}>Unlock</Button>
              </li>
            ))}
            {r.theirs.map((l) => (
              <li key={l.path} className="flex items-center gap-2"><Badge tone="warn">{l.owner || "colleague"}</Badge><span>{l.path}</span></li>
            ))}
          </ul>
          {r.warnings.map((w) => <p key={w} className="text-xs text-warning">{w}</p>)}
        </div>
      ) : null)}
      {unlock.error && <p className="text-sm text-destructive">{String(unlock.error)}</p>}
    </Card>
  );
}
