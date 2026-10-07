import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Job } from "../../app/api";
import { Badge, Button, Card, Empty, Field, inputClass, KeyValue } from "../../ui/components";
import { LockConflicts, LocksCard } from "./Locks";

type GitStatus = Record<string, { path: string; git: boolean; branch?: string; head?: string; dirty?: string[]; pins?: { path: string; commit: string; state: string }[]; ahead?: number | null; behind?: number | null; upstream?: string | null }>;
type RepoChange = { name: string; path: string; kind: string; branch: string; files: string[]; reports: { command: string }[]; commit_message: string; pr_title: string; pr_body: string; commit: string | null; pr_url: string | null; pr_state: string | null; merge_commit: string | null; pin_bumped: string | null; locked?: string[]; notes: string[] };
type ChangeSet = { id: string; topic: string; comment: string; created: number; state: string; repos: RepoChange[] };

const stateTone = (s: string) => (s === "done" || s === "merged" ? "ok" : s === "draft" ? "muted" : "warn");

export function GitPage() {
  const queryClient = useQueryClient();
  const git = useQuery({ queryKey: ["git"], queryFn: () => api.get<GitStatus>("/api/doqs/git/status"), refetchInterval: 10000 });
  const sets = useQuery({ queryKey: ["git", "changesets"], queryFn: () => api.get<ChangeSet[]>("/api/doqs/git/changesets") });
  const [form, setForm] = useState({ topic: "", comment: "" });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["git"] });
  const create = useMutation({ mutationFn: () => api.post<ChangeSet>("/api/doqs/git/changesets", form), onSuccess: () => { setForm({ topic: "", comment: "" }); refresh(); } });
  const act = useMutation({ mutationFn: ({ id, action }: { id: string; action: string }) => api.post<Job | ChangeSet>(`/api/doqs/git/changesets/${id}/${action}`), onSuccess: refresh });
  const saveText = useMutation({ mutationFn: (body: { id: string; repo: string; commit_message?: string; pr_title?: string; pr_body?: string }) => api.put<ChangeSet>(`/api/doqs/git/changesets/${body.id}/text`, body), onSuccess: refresh });

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Git</h1>
      <LockConflicts />
      <div className="grid gap-4 md:grid-cols-3">
        {Object.entries(git.data ?? {}).map(([name, repo]) => (
          <Card key={name} title={name}>
            {!repo.git ? <Empty>{repo.path} is not a git checkout.</Empty> : (
              <KeyValue items={[
                ["Branch", <span>{repo.branch} <span className="text-muted-foreground">{repo.head}</span></span>],
                ["Changed files", repo.dirty?.length ? <ul className="text-xs">{repo.dirty.map((d) => <li key={d}>{d}</li>)}</ul> : <Badge tone="ok">clean</Badge>],
                ["Pins", (repo.pins ?? []).length ? (repo.pins ?? []).map((p) => <div key={p.path} className="text-xs">{p.path} <Badge tone={p.state === "pinned" ? "muted" : "warn"}>{p.commit} {p.state}</Badge></div>) : "none"],
              ]} />
            )}
          </Card>
        ))}
      </div>

      <LocksCard />

      <Card title="New change set">
        <p className="mb-3 text-sm text-muted-foreground">One change across the repositories: a branch with the same name in each, a commit per repository in the order private library, public library, machine, then the pull requests. The commit messages and pull request text are generated from what the commands reported, with your comment under "Why it matters".</p>
        <form className="grid gap-3 md:grid-cols-[1fr_2fr_auto]" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <Field label="Topic" hint="becomes the branch name feat/<topic>"><input className={inputClass} value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} /></Field>
          <Field label="Why this change matters, in your words"><input className={inputClass} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} /></Field>
          <div className="self-end"><Button type="submit" disabled={!form.topic || create.isPending}>Create</Button></div>
        </form>
        {create.error && <p className="mt-2 text-sm text-destructive">{String(create.error)}</p>}
      </Card>

      {(sets.data ?? []).map((cs) => (
        <Card key={cs.id} title={<span>{cs.topic} <Badge tone={stateTone(cs.state)}>{cs.state}</Badge></span>}
          actions={<>
            {cs.state === "draft" && <Button onClick={() => act.mutate({ id: cs.id, action: "commit" })}>Commit</Button>}
            {cs.state === "committed" && <Button onClick={() => act.mutate({ id: cs.id, action: "push-pr" })}>Push and open PRs</Button>}
            {(cs.state === "pushed" || cs.state === "merged") && <>
              <Button kind="secondary" onClick={() => act.mutate({ id: cs.id, action: "refresh" })}>Refresh</Button>
              <Button onClick={() => act.mutate({ id: cs.id, action: "bump" })}>Bump pins after merge</Button>
            </>}
          </>}>
          {cs.repos.map((repo) => (
            <details key={repo.name} className="mb-2 rounded-[var(--radius)] border p-3" open={cs.state === "draft"}>
              <summary className="flex cursor-pointer items-center justify-between text-sm">
                <span><b>{repo.name}</b> · {repo.branch} · {repo.files.length} files · {repo.reports.length} commands</span>
                <span className="flex gap-2">
                  {repo.commit && <Badge tone="ok">{repo.commit.slice(0, 10)}</Badge>}
                  {repo.pr_url && <a className="text-primary" href={repo.pr_url} target="_blank" rel="noreferrer">{repo.pr_state ?? "PR"}</a>}
                  {repo.pin_bumped && <Badge tone="ok">pin → {repo.pin_bumped.slice(0, 10)}</Badge>}
                  {(repo.locked ?? []).length > 0 && <Badge tone="muted">{(repo.locked ?? []).length} locked until the merge</Badge>}
                </span>
              </summary>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <Field label="Commit message">
                  <textarea className={`${inputClass} h-24 font-mono text-xs`} defaultValue={repo.commit_message} disabled={!!repo.commit}
                    onBlur={(e) => !repo.commit && e.target.value !== repo.commit_message && saveText.mutate({ id: cs.id, repo: repo.name, commit_message: e.target.value })} />
                </Field>
                <div>
                  <Field label="Pull request title">
                    <input className={inputClass} defaultValue={repo.pr_title} disabled={!!repo.pr_url}
                      onBlur={(e) => !repo.pr_url && e.target.value !== repo.pr_title && saveText.mutate({ id: cs.id, repo: repo.name, pr_title: e.target.value })} />
                  </Field>
                  <Field label="Pull request text" hint="the four headings stay; everything above the notes under 200 words">
                    <textarea className={`${inputClass} h-48 font-mono text-xs`} defaultValue={repo.pr_body} disabled={!!repo.pr_url}
                      onBlur={(e) => !repo.pr_url && e.target.value !== repo.pr_body && saveText.mutate({ id: cs.id, repo: repo.name, pr_body: e.target.value })} />
                  </Field>
                </div>
              </div>
              {repo.files.length > 0 && <ul className="mt-2 text-xs text-muted-foreground">{repo.files.map((f) => <li key={f}>{f}</li>)}</ul>}
              {repo.notes.length > 0 && <ul className="mt-2 text-xs">{repo.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
            </details>
          ))}
          {saveText.error && <p className="text-sm text-destructive">{String(saveText.error)}</p>}
          {act.error && <p className="text-sm text-destructive">{String(act.error)}</p>}
        </Card>
      ))}
    </div>
  );
}
