import { useQuery } from "@tanstack/react-query";
import { api } from "../../app/api";
import { Badge, Card, Empty, KeyValue } from "../../ui/components";

type GitStatus = Record<string, { path: string; git: boolean; branch?: string; head?: string; dirty?: string[]; pins?: { path: string; commit: string; state: string }[]; ahead?: number | null; behind?: number | null; upstream?: string | null }>;

export function GitPage() {
  const git = useQuery({ queryKey: ["git"], queryFn: () => api.get<GitStatus>("/api/doqs/git/status"), refetchInterval: 10000 });
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Git</h1>
      <p className="text-sm text-muted-foreground">The state of each repository. Change sets, generated commit messages and pull requests come in the next slice.</p>
      {Object.entries(git.data ?? {}).map(([name, repo]) => (
        <Card key={name} title={name}>
          {!repo.git ? <Empty>{repo.path} is not a git checkout.</Empty> : (
            <KeyValue items={[
              ["Path", <span className="text-xs">{repo.path}</span>],
              ["Branch", <span>{repo.branch} <span className="text-muted-foreground">{repo.head}</span> {repo.upstream && <span className="text-xs text-muted-foreground">→ {repo.upstream}</span>}</span>],
              ["Ahead / behind", repo.ahead == null ? "no upstream" : `${repo.ahead} / ${repo.behind}`],
              ["Changed files", repo.dirty?.length ? <ul className="text-xs">{repo.dirty.map((d) => <li key={d}>{d}</li>)}</ul> : <Badge tone="ok">clean</Badge>],
              ["Submodule pins", (repo.pins ?? []).length ? (repo.pins ?? []).map((p) => <div key={p.path} className="text-xs">{p.path} <Badge tone={p.state === "pinned" ? "muted" : "warn"}>{p.commit} {p.state}</Badge></div>) : "none"],
            ]} />
          )}
        </Card>
      ))}
    </div>
  );
}
