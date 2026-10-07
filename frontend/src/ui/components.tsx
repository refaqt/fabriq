import type { ReactNode } from "react";

export function Card({ title, children, actions, className = "" }: { title?: ReactNode; children: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <section className={`rounded-[var(--radius)] border bg-card p-4 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-base font-semibold">{title}</h2>
          <div className="flex gap-2">{actions}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Badge({ tone = "muted", children }: { tone?: "muted" | "ok" | "warn" | "bad"; children: ReactNode }) {
  const tones = {
    muted: "bg-muted text-foreground",
    ok: "bg-primary/20 text-primary",
    warn: "bg-warning/20 text-warning",
    bad: "bg-destructive/20 text-destructive",
  };
  return <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Button({ children, onClick, kind = "primary", disabled, type = "button" }: {
  children: ReactNode; onClick?: () => void; kind?: "primary" | "secondary" | "ghost" | "danger"; disabled?: boolean; type?: "button" | "submit";
}) {
  const kinds = {
    primary: "bg-primary text-primary-foreground hover:brightness-110",
    secondary: "bg-secondary text-foreground hover:bg-muted",
    ghost: "text-muted-foreground hover:text-foreground",
    danger: "bg-destructive/20 text-destructive hover:bg-destructive/30",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`rounded-[var(--radius)] px-3 py-1.5 text-sm font-medium transition disabled:opacity-50 ${kinds[kind]}`}>
      {children}
    </button>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-muted-foreground">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted-foreground">{hint}</span>}
    </label>
  );
}

export const inputClass = "w-full rounded-[var(--radius)] border bg-input px-3 py-1.5 text-sm text-foreground outline-none focus:ring-2 focus:ring-primary";

export function Table({ headers, rows }: { headers: string[]; rows: ReactNode[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-muted-foreground">
            {headers.map((h) => <th key={h} className="border-b py-1.5 pr-3 font-medium">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((cells, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0">
              {cells.map((c, j) => <td key={j} className="py-1.5 pr-3 align-top">{c}</td>)}
            </tr>
          ))}
          {rows.length === 0 && <tr><td className="py-2 text-muted-foreground" colSpan={headers.length}>Nothing yet.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}

export function KeyValue({ items }: { items: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      {items.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="break-words">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Stepper({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol className="mb-4 flex flex-wrap gap-2 text-xs">
      {steps.map((s, i) => (
        <li key={s} className={`rounded-full px-3 py-1 ${i === current ? "bg-primary text-primary-foreground" : i < current ? "bg-primary/20 text-primary" : "bg-muted text-muted-foreground"}`}>
          {i + 1}. {s}
        </li>
      ))}
    </ol>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-[var(--radius)] border border-dashed p-4 text-sm text-muted-foreground">{children}</p>;
}
