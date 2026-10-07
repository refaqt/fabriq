import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { api, type Job, type Module, type Report } from "../../app/api";
import { Badge, Button, Card, Empty, Field, inputClass, KeyValue, Table } from "../../ui/components";
import { DiagramView } from "./DiagramView";
import { ReportView } from "./JobDrawer";

export function ModulePage() {
  const slug = decodeURIComponent(useLocation().pathname.replace(/^\/modules\//, ""));
  const module = useQuery({ queryKey: ["model", slug], queryFn: () => api.get<Module>(`/api/doqs/model/modules/${slug}`) });
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["model"] });
  const [part, setPart] = useState("");
  const [usePart, setUsePart] = useState({ part: "", qty: "1", name: "", category: "MEC", sysml: "", usages: "" });
  const [iface, setIface] = useState({ name: "", a: "", b: "", doc: "", outside: "" });
  const [lastReport, setLastReport] = useState<Report | null>(null);
  const scaffoldPart = useMutation({ mutationFn: () => api.post<Job>(`/api/doqs/modules/${slug}/parts`, { part }) });
  const usePartM = useMutation({
    mutationFn: () => api.post<Report>(`/api/doqs/modules/${slug}/use-part`, { ...usePart, usages: usePart.usages.split(",").map((s) => s.trim()).filter(Boolean), sysml: usePart.sysml || undefined, name: usePart.name || undefined }),
    onSuccess: (r) => { setLastReport(r); refresh(); },
  });
  const addIface = useMutation({ mutationFn: () => api.post<Job>(`/api/doqs/modules/${slug}/interfaces`, { ...iface, outside: iface.outside || undefined, doc: iface.doc || undefined }) });
  const m = module.data;
  if (!m) return <Empty>{module.error ? String(module.error) : "Reading the module…"}</Empty>;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{m.name ?? m.slug}</h1>
        <p className="text-sm text-muted-foreground">{m.slug} · version {m.version}</p>
        <p className="mt-1 text-sm">{m.function}</p>
      </div>

      <Card title="Block diagram"><DiagramView module={m} /></Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Own parts">
          <Table headers={["Part", "SysML", "File", "Frames", "Fingerprint"]} rows={m.parts.map((p) => [
            p.name, p.sysml ?? <Badge tone="warn">none</Badge>,
            p.exists ? <span className="text-xs">{p.file}</span> : <Badge tone="warn">no file yet</Badge>,
            p.frames.length ? p.frames.map((f) => <Badge key={f.name} tone={f.label.startsWith("IF_") ? "ok" : "bad"}>{f.label}</Badge>) : <span className="text-muted-foreground">none</span>,
            !p.fingerprint ? "" : !p.fingerprint.exists ? <Badge tone="warn">missing</Badge> : p.fingerprint.current ? <Badge tone="ok">current</Badge> : <Badge tone="bad">stale</Badge>,
          ])} />
          <form className="mt-3 flex items-end gap-2" onSubmit={(e) => { e.preventDefault(); scaffoldPart.mutate(); }}>
            <Field label="New own part" hint="kebab-case; FreeCAD makes the empty document"><input className={inputClass} value={part} onChange={(e) => setPart(e.target.value)} /></Field>
            <Button type="submit" disabled={!part || scaffoldPart.isPending}>Create part</Button>
          </form>
        </Card>
        <Card title="Bought parts">
          <Table headers={["BOM", "Library part", "SysML", "Terms", "Wrapper", "Frames"]} rows={m.bought.map((b) => [
            b.bom, <span className="text-xs">{b.part}</span>, b.sysml,
            b.error ? <Badge tone="bad">{b.error}</Badge> : <Badge tone={b.terms === "redistributable" ? "ok" : "muted"}>{b.terms}</Badge>,
            b.wrapper_exists ? <Badge tone="ok">yes</Badge> : <Badge tone="warn">missing</Badge>,
            (b.frames ?? []).map((f) => <Badge key={f.name} tone="ok">{f.label}</Badge>),
          ])} />
          <form className="mt-3 grid gap-2 md:grid-cols-3" onSubmit={(e) => { e.preventDefault(); usePartM.mutate(); }}>
            <Field label="Library reference" hint="stoq:brand/family#part-number"><input className={inputClass} value={usePart.part} onChange={(e) => setUsePart({ ...usePart, part: e.target.value })} /></Field>
            <Field label="Quantity"><input className={inputClass} value={usePart.qty} onChange={(e) => setUsePart({ ...usePart, qty: e.target.value })} /></Field>
            <Field label="Category"><select className={inputClass} value={usePart.category} onChange={(e) => setUsePart({ ...usePart, category: e.target.value })}>{["MEC", "STD", "ELC", "MOT", "HW", "PRF", "BRK", "SW"].map((c) => <option key={c}>{c}</option>)}</select></Field>
            <Field label="Name in the BOM"><input className={inputClass} value={usePart.name} onChange={(e) => setUsePart({ ...usePart, name: e.target.value })} /></Field>
            <Field label="SysML part def" hint="default: from the family"><input className={inputClass} value={usePart.sysml} onChange={(e) => setUsePart({ ...usePart, sysml: e.target.value })} /></Field>
            <Field label="Usages" hint="comma-separated, like railA,railB"><input className={inputClass} value={usePart.usages} onChange={(e) => setUsePart({ ...usePart, usages: e.target.value })} /></Field>
            <div className="md:col-span-3"><Button type="submit" disabled={!usePart.part || usePartM.isPending}>Use part</Button>
              {usePartM.error && <span className="ml-3 text-sm text-destructive">{String(usePartM.error)}</span>}</div>
          </form>
          {lastReport && <div className="mt-3 border-t pt-3"><ReportView report={lastReport} /></div>}
        </Card>
      </div>

      <Card title="Interfaces">
        <div className="grid gap-4 lg:grid-cols-2">
          <div>
            <KeyValue items={[
              ["Provides", m.provides.length ? m.provides.map((i) => <Badge key={i.name} tone="ok">{i.name} {i.version}</Badge>) : "none"],
              ["Consumes", m.consumes.length ? m.consumes.map((i) => <Badge key={i.name} tone="muted">{i.name} {i.version}</Badge>) : "none"],
              ["Port defs", m.sysml.interfaces.map((i) => <div key={i.name}><span>{i.name}</span>{i.doc && <span className="text-xs text-muted-foreground"> — {i.doc}</span>}</div>)],
              ["Connections", m.sysml.connections.map((c) => <div key={c.a + c.b} className="text-xs">{c.a} ⇄ {c.b}</div>)],
            ]} />
          </div>
          <form className="grid gap-2" onSubmit={(e) => { e.preventDefault(); addIface.mutate(); }}>
            <Field label="Interface name" hint="like RailMount; becomes RailMountInterface_v1"><input className={inputClass} value={iface.name} onChange={(e) => setIface({ ...iface, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-2">
              <Field label="Side A (plain port)" hint="usage.port, like base.railMount"><input className={inputClass} value={iface.a} onChange={(e) => setIface({ ...iface, a: e.target.value })} /></Field>
              <Field label="Side B (conjugate port)" hint="usage.port, like rail.baseMount"><input className={inputClass} value={iface.b} onChange={(e) => setIface({ ...iface, b: e.target.value })} /></Field>
            </div>
            <Field label="What it is"><input className={inputClass} value={iface.doc} onChange={(e) => setIface({ ...iface, doc: e.target.value })} /></Field>
            <Field label="Faces outside the module?"><select className={inputClass} value={iface.outside} onChange={(e) => setIface({ ...iface, outside: e.target.value })}><option value="">no</option><option value="provides">provides</option><option value="consumes">consumes</option></select></Field>
            <div><Button type="submit" disabled={!iface.name || !iface.a || !iface.b || addIface.isPending}>Add interface</Button>
              <span className="ml-3 text-xs text-muted-foreground">Writes SysML, okh.toml and a frame IF_&lt;port&gt; in each part file.</span></div>
          </form>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Requirements">
          <Table headers={["Id", "Name", "Says", "Constraint"]} rows={m.sysml.requirements.filter((r) => r.short).map((r) => [
            <Badge tone="muted">{r.short}</Badge>, r.name, <span className="text-xs">{r.doc}</span>, <code className="text-xs">{r.constraint}</code>,
          ])} />
        </Card>
        <Card title="Bill of materials">
          <Table headers={["Id", "Name", "Qty", "Brand", "Part"]} rows={m.bom.map((r) => [r.id, r.name, r.qty, r.brand, <span className="text-xs">{r.part}</span>])} />
        </Card>
      </div>
      {m.problems.length > 0 && <Card title="Problems"><ul className="list-disc pl-5 text-sm">{m.problems.map((p) => <li key={p}>{p}</li>)}</ul></Card>}
    </div>
  );
}
