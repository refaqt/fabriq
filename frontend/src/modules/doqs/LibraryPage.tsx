import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, type Job, type Library, type LibraryPart } from "../../app/api";
import { Badge, Button, Card, Empty, Field, inputClass, Table } from "../../ui/components";

const termsTone = (t?: string) => (t === "redistributable" ? "ok" : t === "internal" || t === "private" ? "warn" : "muted");

export function LibraryPage() {
  const libraries = useQuery({ queryKey: ["library"], queryFn: () => api.get<Library[]>("/api/doqs/library") });
  const [selected, setSelected] = useState<{ library: string; part: LibraryPart } | null>(null);
  const [frames, setFrames] = useState("IF_mount");
  const wrap = useMutation({ mutationFn: () => api.post<Job>("/api/doqs/library/wrap", { library: selected?.library, part: selected?.part.reference, frames: frames.split(",").map((s) => s.trim()).filter(Boolean) }) });

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <h1 className="text-2xl font-semibold">Parts library</h1>
        <Link to="/library/add"><Button>Add a supplier part</Button></Link>
      </div>
      {(libraries.data ?? []).map((lib) => (
        <Card key={lib.name} title={<span>{lib.name} <span className="text-xs font-normal text-muted-foreground">mounted {lib.mounted ? "yes" : "no"} · public {lib.public ? "beside" : "—"} · private {lib.private ? "beside" : "—"}</span></span>}>
          {lib.brands.length === 0 && <Empty>No brands yet.</Empty>}
          {lib.brands.map((brand) => (
            <div key={brand.slug} className="mb-4">
              <h3 className="mb-1 font-medium">{brand.name ?? brand.slug} <span className="text-xs text-muted-foreground">{brand.reviews.length} terms reviews</span></h3>
              {brand.families.map((family) => (
                <div key={family.slug} className="mb-2 ml-3">
                  <div className="text-sm text-muted-foreground">{family.name ?? family.slug} · {family.function}</div>
                  <Table headers={["Part number", "Description", "Mass g", "Terms (public / private)", "Wrapper", "Frames", ""]} rows={family.parts.map((p) => [
                    <code className="text-xs">{p.pn}</code>, <span className="text-xs">{p.description}</span>, p.unit_mass_g,
                    <span><Badge tone={termsTone(p.where.public?.terms ?? p.where.mounted?.terms)}>{p.where.public?.terms ?? p.where.mounted?.terms ?? "—"}</Badge>{" "}
                      <Badge tone={termsTone(p.where.private?.terms)}>{p.where.private?.terms ?? "—"}</Badge></span>,
                    Object.values(p.where).some((w) => w.cad_exists) ? <Badge tone="ok">yes</Badge> : <Badge tone="warn">none</Badge>,
                    (p.where.private?.frames ?? p.where.public?.frames ?? p.where.mounted?.frames ?? []).map((f) => <Badge key={f.name} tone={f.label.startsWith("IF_") ? "ok" : "bad"}>{f.label}</Badge>),
                    <Button kind="secondary" onClick={() => setSelected({ library: lib.name, part: p })}>Wrap…</Button>,
                  ])} />
                </div>
              ))}
            </div>
          ))}
        </Card>
      ))}
      {selected && (
        <Card title={`Wrap ${selected.part.pn} in FreeCAD`} actions={<Button kind="ghost" onClick={() => setSelected(null)}>Close</Button>}>
          <p className="mb-2 text-sm text-muted-foreground">Builds the FreeCAD wrapper from the STEP file in a FreeCAD window, so the brand's colours survive, with one frame per attachment place at the origin. You then place the frames.</p>
          <Field label="Frames" hint="comma-separated IF_ labels, one per place another part attaches"><input className={inputClass} value={frames} onChange={(e) => setFrames(e.target.value)} /></Field>
          <div className="mt-2"><Button onClick={() => wrap.mutate()} disabled={wrap.isPending}>Start</Button>
            {wrap.data && <span className="ml-3 text-sm text-muted-foreground">Job started: {wrap.data.title}</span>}
            {wrap.error && <span className="ml-3 text-sm text-destructive">{String(wrap.error)}</span>}</div>
        </Card>
      )}
    </div>
  );
}
