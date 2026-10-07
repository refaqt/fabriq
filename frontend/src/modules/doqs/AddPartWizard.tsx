import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, type Job, type Library } from "../../app/api";
import { Button, Card, Field, inputClass, Stepper } from "../../ui/components";

const STEPS = ["Brand and family", "The part", "Files", "Terms", "Start"];

export function AddPartWizard() {
  const libraries = useQuery({ queryKey: ["library"], queryFn: () => api.get<Library[]>("/api/doqs/library") });
  const navigate = useNavigate();
  const [step, setStep] = useState(0);
  const [f, setF] = useState({
    library: "", brand: "", brand_name: "", website: "", family: "", family_name: "", function: "",
    pn: "", description: "", spec: "", mass_g: "", revision: "A", notes: "",
    source_url: "", terms_url: "", decision: "customers", basis: "terms", reviewer: "",
  });
  const [files, setFiles] = useState<{ step?: File; datasheet?: File; terms_pdf?: File; licence?: File }>({});
  const set = (key: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [key]: e.target.value });
  const submit = useMutation({
    mutationFn: () => {
      const form = new FormData();
      Object.entries(f).forEach(([k, v]) => form.append(k, v));
      Object.entries(files).forEach(([k, file]) => file && form.append(k, file));
      return api.upload<Job>("/api/doqs/library/intake", form);
    },
    onSuccess: () => navigate("/library"),
  });
  const lib = libraries.data?.find((l) => l.name === (f.library || libraries.data?.[0]?.name));
  const brands = lib?.brands ?? [];
  const families = brands.find((b) => b.slug === f.brand)?.families ?? [];
  const fileInput = (key: keyof typeof files, label: string, hint: string, accept?: string) => (
    <Field label={label} hint={hint}>
      <input type="file" accept={accept} className="text-sm" onChange={(e) => setFiles({ ...files, [key]: e.target.files?.[0] })} />
      {files[key] && <span className="ml-2 text-xs text-muted-foreground">{files[key]?.name}</span>}
    </Field>
  );

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-semibold">Add a supplier part</h1>
      <p className="text-sm text-muted-foreground">One pass records the part in the private library and the public one: rows, checksums, the terms review and the evidence. Nothing is overwritten, and a rerun changes nothing.</p>
      <Stepper steps={STEPS} current={step} />
      <Card>
        {step === 0 && (
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Library"><select className={inputClass} value={f.library} onChange={set("library")}>{(libraries.data ?? []).map((l) => <option key={l.name} value={l.name}>{l.name}</option>)}</select></Field>
            <Field label="Brand" hint="kebab-case slug; a new one is created"><input className={inputClass} list="brands" value={f.brand} onChange={set("brand")} />
              <datalist id="brands">{brands.map((b) => <option key={b.slug} value={b.slug} />)}</datalist></Field>
            <Field label="Brand name (new brand)"><input className={inputClass} value={f.brand_name} onChange={set("brand_name")} /></Field>
            <Field label="Brand website (new brand)"><input className={inputClass} value={f.website} onChange={set("website")} /></Field>
            <Field label="Family" hint="kebab-case slug, like hgl-block"><input className={inputClass} list="families" value={f.family} onChange={set("family")} />
              <datalist id="families">{families.map((fam) => <option key={fam.slug} value={fam.slug} />)}</datalist></Field>
            <Field label="Family name (new family)"><input className={inputClass} value={f.family_name} onChange={set("family_name")} /></Field>
            <Field label="What the family is (new family)"><input className={inputClass} value={f.function} onChange={set("function")} /></Field>
          </div>
        )}
        {step === 1 && (
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Part number" hint="the brand's own, verbatim"><input className={inputClass} value={f.pn} onChange={set("pn")} /></Field>
            <Field label="Description"><input className={inputClass} value={f.description} onChange={set("description")} /></Field>
            <Field label="Spec" hint="sizes and ratings in one line"><input className={inputClass} value={f.spec} onChange={set("spec")} /></Field>
            <Field label="Mass (g)"><input className={inputClass} value={f.mass_g} onChange={set("mass_g")} /></Field>
            <Field label="Revision"><input className={inputClass} value={f.revision} onChange={set("revision")} /></Field>
            <Field label="Notes"><input className={inputClass} value={f.notes} onChange={set("notes")} /></Field>
          </div>
        )}
        {step === 2 && (
          <div className="grid gap-3">
            {fileInput("step", "STEP file", "goes to cad/original/<part number>.step", ".step,.stp")}
            {fileInput("datasheet", "Datasheet", "goes to docs/datasheets/", ".pdf")}
            <Field label="Where the brand publishes the file" hint="a public address makes the public row fetch-only instead of private"><input className={inputClass} value={f.source_url} onChange={set("source_url")} /></Field>
          </div>
        )}
        {step === 3 && (
          <div className="grid gap-3 md:grid-cols-2">
            <Field label="Decision" hint="public: files in both libraries · customers / internal: files in the private one only">
              <select className={inputClass} value={f.decision} onChange={set("decision")}><option value="public">public</option><option value="customers">customers</option><option value="internal">internal</option></select></Field>
            <Field label="Basis"><select className={inputClass} value={f.basis} onChange={set("basis")}><option value="terms">their published terms</option><option value="permission">a written permission</option><option value="none">nothing allows it</option></select></Field>
            <Field label="Terms page that was read"><input className={inputClass} value={f.terms_url} onChange={set("terms_url")} /></Field>
            <Field label="Reviewer" hint="the named person who approves the review in the pull request"><input className={inputClass} value={f.reviewer} onChange={set("reviewer")} /></Field>
            {fileInput("terms_pdf", "Saved copy of the terms", "stored as evidence in the private library", ".pdf")}
            {fileInput("licence", "The supplier's licence text", "optional", "*")}
          </div>
        )}
        {step === 4 && (
          <div className="text-sm">
            <p>Ready: <b>{f.brand}/{f.family}#{f.pn}</b>, decision <b>{f.decision}</b> on basis <b>{f.basis}</b>, reviewed by <b>{f.reviewer || "?"}</b>.</p>
            <p className="mt-2 text-muted-foreground">Then: wrap the STEP in FreeCAD from the library page, open the library pull requests, and use the part in a module.</p>
            {submit.error && <p className="mt-2 text-destructive">{String(submit.error)}</p>}
          </div>
        )}
        <div className="mt-4 flex justify-between">
          <Button kind="secondary" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0}>Back</Button>
          {step < STEPS.length - 1
            ? <Button onClick={() => setStep((s) => s + 1)} disabled={(step === 0 && (!f.brand || !f.family)) || (step === 1 && (!f.pn || !f.description)) || (step === 3 && !f.reviewer)}>Next</Button>
            : <Button onClick={() => submit.mutate()} disabled={submit.isPending}>Add the part</Button>}
        </div>
      </Card>
    </div>
  );
}
