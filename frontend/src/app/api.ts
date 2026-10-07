/** The fabriq API, typed as far as the pages need. */

export type Job = {
  id: string;
  kind: string;
  title: string;
  state: "queued" | "running" | "done" | "failed" | "cancelled";
  steps: { name: string; state: string; log: string[] }[];
  result: Report | Record<string, unknown> | null;
  error: string | null;
  created: number;
  finished: number | null;
};

export type Report = {
  command: string;
  ok: boolean;
  dry_run: boolean;
  written: string[];
  edited: string[];
  unchanged: string[];
  warnings: string[];
  errors: string[];
  next_steps: string[];
  facts: Record<string, unknown>;
};

export type Frame = { name: string; label: string };

export type Part = {
  name: string;
  sysml: string | null;
  file: string | null;
  exists: boolean;
  frames: Frame[];
  fingerprint: { exists: boolean; current: boolean; saved?: boolean; unlinked?: number } | null;
  build_script: boolean;
};

export type Bought = {
  bom: string;
  part: string;
  sysml: string | null;
  description?: string;
  terms?: string;
  wrapper?: string | null;
  wrapper_exists?: boolean;
  frames?: Frame[];
  error?: string;
};

export type SysmlPart = {
  name: string;
  doc: string | null;
  ports: { name: string; type: string; conjugated: boolean }[];
  usages: { name: string; type: string }[];
  connections: string[];
};

export type Module = {
  slug: string;
  name: string;
  version: string;
  function: string;
  provides: { name: string; version: string; description?: string }[];
  consumes: { name: string; version: string; description?: string }[];
  components: string[];
  parts: Part[];
  bought: Bought[];
  bom: Record<string, string>[];
  params: Record<string, string>[];
  sysml: {
    files: string[];
    interfaces: { name: string; version: number | null; doc: string | null }[];
    parts: SysmlPart[];
    connections: { owner: string; a: string; b: string }[];
    requirements: { short: string | null; name: string; doc: string | null; package: string; constraint: string | null }[];
  };
  role: Record<string, unknown> | null;
  problems: string[];
};

export type LibraryPart = {
  pn: string;
  description: string;
  spec: string;
  unit_mass_g: string;
  status: string;
  reference: string;
  where: Record<string, { terms: string; cad: string; cad_exists: boolean; frames: Frame[]; datasheet: string }>;
};

export type Library = {
  name: string;
  mounted: string | null;
  public: string | null;
  private: string | null;
  brands: {
    slug: string;
    name: string;
    website: string | null;
    reviews: Record<string, string>[];
    families: { slug: string; name: string; function: string; provides: string[]; parts: LibraryPart[] }[];
  }[];
};

export type Model = {
  root: string;
  kind: string;
  modules: Module[];
  libraries: Library[];
  builds: { id: string }[];
  problems: string[];
};

export type Workspace = {
  root: string;
  name: string;
  kind: string;
  fabriq: string;
  doqs: { ok: boolean; api_version: number[] | null; error: string | null };
  libraries: { name: string; mounted: string | null; public: string | null; private: string | null }[];
  modules: { name: string; title: string; nav: { label: string; path: string; icon: string }[] }[];
};

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep the status text */
    }
    throw new Error(`${response.status}: ${detail}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => fetch(path).then((r) => handle<T>(r)),
  post: <T>(path: string, body?: unknown) =>
    fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }).then((r) => handle<T>(r)),
  put: <T>(path: string, body?: unknown) =>
    fetch(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) }).then((r) => handle<T>(r)),
  upload: <T>(path: string, form: FormData) => fetch(path, { method: "POST", body: form }).then((r) => handle<T>(r)),
};
