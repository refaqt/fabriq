import { useState } from "react";
import type { Job, Report } from "../../app/api";
import { Badge, Button } from "../../ui/components";

const tone = (state: Job["state"]) => (state === "done" ? "ok" : state === "failed" ? "bad" : state === "running" ? "warn" : "muted");

export function ReportView({ report }: { report: Report }) {
  const list = (title: string, items: string[], t: "ok" | "warn" | "bad" | "muted") =>
    items.length ? (
      <div className="mb-2">
        <div className="text-xs text-muted-foreground">{title}</div>
        <ul className="ml-3 list-disc text-xs">{items.map((i) => <li key={i}><Badge tone={t}>{i}</Badge></li>)}</ul>
      </div>
    ) : null;
  return (
    <div className="text-sm">
      {list("Wrote", report.written, "ok")}
      {list("Changed", report.edited, "ok")}
      {list("Left alone", report.unchanged, "muted")}
      {list("Warnings", report.warnings, "warn")}
      {list("Errors", report.errors, "bad")}
      {report.next_steps.length > 0 && (
        <div>
          <div className="text-xs text-muted-foreground">Next</div>
          <ol className="ml-4 list-decimal text-xs">{report.next_steps.map((s) => <li key={s}>{s}</li>)}</ol>
        </div>
      )}
    </div>
  );
}

function isReport(value: unknown): value is Report {
  return !!value && typeof value === "object" && "written" in (value as object) && "command" in (value as object);
}

export function JobDrawer({ jobs, onClose }: { jobs: Job[]; onClose: () => void }) {
  const [open, setOpen] = useState<string | null>(jobs[0]?.id ?? null);
  return (
    <aside className="fixed inset-y-0 right-0 z-20 flex w-[28rem] max-w-full flex-col border-l bg-card shadow-2xl">
      <header className="flex items-center justify-between border-b p-3">
        <h2 className="font-semibold">Jobs</h2>
        <Button kind="ghost" onClick={onClose}>Close</Button>
      </header>
      <div className="flex-1 overflow-y-auto p-3">
        {jobs.length === 0 && <p className="text-sm text-muted-foreground">No jobs yet.</p>}
        {jobs.map((job) => (
          <div key={job.id} className="mb-2 rounded-[var(--radius)] border p-2">
            <button className="flex w-full items-center justify-between text-left text-sm" onClick={() => setOpen(open === job.id ? null : job.id)}>
              <span className="truncate">{job.title}</span>
              <Badge tone={tone(job.state)}>{job.state}</Badge>
            </button>
            {open === job.id && (
              <div className="mt-2 border-t pt-2">
                {job.steps.map((step, i) => (
                  <div key={i} className="mb-1">
                    <div className="flex items-center gap-2 text-xs"><Badge tone={step.state === "failed" ? "bad" : step.state === "done" ? "ok" : "warn"}>{step.state}</Badge>{step.name}</div>
                    {step.log.length > 0 && <pre className="mt-1 max-h-48 overflow-auto rounded bg-background p-2 text-[11px] leading-snug text-muted-foreground">{step.log.join("\n")}</pre>}
                  </div>
                ))}
                {job.error && <p className="text-xs text-destructive">{job.error}</p>}
                {isReport(job.result) && <ReportView report={job.result} />}
              </div>
            )}
          </div>
        ))}
      </div>
    </aside>
  );
}
