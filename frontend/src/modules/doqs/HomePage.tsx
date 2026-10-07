import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type Job, type Model, type Workspace } from "../../app/api";
import { Badge, Button, Card, Empty, KeyValue } from "../../ui/components";

type GitStatus = Record<string, { git: boolean; branch?: string; head?: string; dirty?: string[]; pins?: { path: string; commit: string; state: string }[]; ahead?: number | null; behind?: number | null }>;
type FreeCad = { rpc: boolean; gui: string | null; cmd: string | null; mode: string };

export function HomePage() {
  const workspace = useQuery({ queryKey: ["workspace"], queryFn: () => api.get<Workspace>("/api/workspace") });
  const model = useQuery({ queryKey: ["model"], queryFn: () => api.get<Model>("/api/doqs/model") });
  const git = useQuery({ queryKey: ["git"], queryFn: () => api.get<GitStatus>("/api/doqs/git/status"), refetchInterval: 15000 });
  const freecad = useQuery({ queryKey: ["freecad"], queryFn: () => api.get<FreeCad>("/api/doqs/freecad"), refetchInterval: 15000 });
  const check = useMutation({ mutationFn: () => api.post<Job>("/api/doqs/check") });
  const generate = useMutation({ mutationFn: () => api.post<Job>("/api/doqs/generate") });

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{workspace.data?.name ?? "Workspace"}</h1>
          <p className="text-sm text-muted-foreground">{workspace.data?.root}</p>
        </div>
        <div className="flex gap-2">
          <Button kind="secondary" onClick={() => generate.mutate()} disabled={generate.isPending}>Generate</Button>
          <Button onClick={() => check.mutate()} disabled={check.isPending}>Run check</Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {Object.entries(git.data ?? {}).map(([name, repo]) => (
          <Card key={name} title={name}>
            {!repo.git ? <Empty>Not a git checkout.</Empty> : (
              <KeyValue items={[
                ["Branch", <span>{repo.branch} <span className="text-muted-foreground">{repo.head}</span></span>],
                ["Changes", repo.dirty?.length ? <Badge tone="warn">{repo.dirty.length} files</Badge> : <Badge tone="ok">clean</Badge>],
                ["Remote", repo.ahead == null ? "no upstream" : `${repo.ahead} ahead · ${repo.behind} behind`],
                ["Pins", (repo.pins ?? []).length ? (repo.pins ?? []).map((p) => (
                  <div key={p.path} className="flex gap-2"><span>{p.path}</span><Badge tone={p.state === "pinned" ? "muted" : "warn"}>{p.commit} {p.state}</Badge></div>
                )) : "none"],
              ]} />
            )}
          </Card>
        ))}
        <Card title="FreeCAD">
          {freecad.data ? (
            <KeyValue items={[
              ["Open window", freecad.data.rpc ? <Badge tone="ok">answers on the RPC port</Badge> : <Badge tone="muted">not reachable</Badge>],
              ["Binary", freecad.data.gui ?? freecad.data.cmd ?? <Badge tone="bad">none found</Badge>],
              ["Mode", freecad.data.mode],
            ]} />
          ) : <Empty>Asking…</Empty>}
        </Card>
        <Card title="Design">
          {model.data ? (
            <KeyValue items={[
              ["Modules", <Link className="text-primary" to="/modules">{model.data.modules.length}</Link>],
              ["Own parts", model.data.modules.reduce((n, m) => n + m.parts.length, 0)],
              ["Bought parts", model.data.modules.reduce((n, m) => n + m.bought.length, 0)],
              ["Libraries", <Link className="text-primary" to="/library">{model.data.libraries.map((l) => l.name).join(", ") || "none"}</Link>],
              ["Builds", model.data.builds.length],
              ["Problems", model.data.problems.length ? <Badge tone="warn">{model.data.problems.length}</Badge> : <Badge tone="ok">none</Badge>],
            ]} />
          ) : <Empty>Reading the design…</Empty>}
        </Card>
      </div>

      {model.data && model.data.problems.length > 0 && (
        <Card title="Problems the read model sees">
          <ul className="list-disc pl-5 text-sm">{model.data.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </Card>
      )}
    </div>
  );
}
