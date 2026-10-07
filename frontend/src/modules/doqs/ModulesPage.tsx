import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type Model, type Report } from "../../app/api";
import { Badge, Button, Card, Field, inputClass, Table } from "../../ui/components";
import { ReportView } from "./JobDrawer";

export function ModulesPage() {
  const model = useQuery({ queryKey: ["model"], queryFn: () => api.get<Model>("/api/doqs/model") });
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ slug: "", name: "", function: "", parent: "" });
  const [report, setReport] = useState<Report | null>(null);
  const scaffold = useMutation({
    mutationFn: () => api.post<Report>("/api/doqs/modules", { ...form, parent: form.parent || undefined }),
    onSuccess: (r) => { setReport(r); queryClient.invalidateQueries({ queryKey: ["model"] }); },
  });
  const modules = model.data?.modules ?? [];

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Modules</h1>
      <Card title="Every module in the design">
        <Table headers={["Module", "Version", "Own parts", "Bought parts", "Interfaces", "Requirements", "Problems"]}
          rows={modules.map((m) => [
            <Link className="text-primary" to={`/modules/${m.slug}`}>{m.name ?? m.slug}<div className="text-xs text-muted-foreground">{m.slug}</div></Link>,
            m.version,
            m.parts.length,
            m.bought.length,
            <span>{m.provides.length} out · {m.consumes.length} in · {m.sysml.connections.length} inside</span>,
            m.sysml.requirements.filter((r) => r.short).length,
            m.problems.length ? <Badge tone="warn">{m.problems.length}</Badge> : <Badge tone="ok">none</Badge>,
          ])} />
      </Card>
      <Card title="New module">
        <form className="grid gap-3 md:grid-cols-4" onSubmit={(e) => { e.preventDefault(); scaffold.mutate(); }}>
          <Field label="Slug" hint="kebab-case, like guide-block"><input className={inputClass} value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} required /></Field>
          <Field label="Name"><input className={inputClass} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
          <Field label="What it does"><input className={inputClass} value={form.function} onChange={(e) => setForm({ ...form, function: e.target.value })} /></Field>
          <Field label="Parent module" hint="empty for the machine root">
            <select className={inputClass} value={form.parent} onChange={(e) => setForm({ ...form, parent: e.target.value })}>
              <option value="">(root)</option>
              {modules.filter((m) => m.slug !== ".").map((m) => <option key={m.slug} value={m.slug}>{m.slug}</option>)}
            </select>
          </Field>
          <div className="md:col-span-4"><Button type="submit" disabled={scaffold.isPending || !form.slug}>Create module</Button>
            {scaffold.error && <span className="ml-3 text-sm text-destructive">{String(scaffold.error)}</span>}</div>
        </form>
        {report && <div className="mt-3 border-t pt-3"><ReportView report={report} /></div>}
      </Card>
    </div>
  );
}
