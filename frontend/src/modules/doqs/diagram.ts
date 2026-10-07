import dagre from "dagre";
import type { Module } from "../../app/api";

/** A block diagram of one module: a node per part usage, a handle per port, an edge per connect. */
export type DiagramNode = { id: string; label: string; type: string; bought: boolean; ports: { name: string; conjugated: boolean; type: string }[]; x: number; y: number };
export type DiagramEdge = { id: string; source: string; sourcePort: string; target: string; targetPort: string; label: string };

export function diagramOf(module: Module): { nodes: DiagramNode[]; edges: DiagramEdge[] } {
  const defs = new Map(module.sysml.parts.map((p) => [p.name, p]));
  const boughtDefs = new Set(module.bought.map((b) => b.sysml).filter(Boolean));
  const assemblyName = module.sysml.parts.find((p) => p.usages.length > 0)?.name;
  const assembly = assemblyName ? defs.get(assemblyName) : undefined;
  const usages = assembly?.usages ?? [];
  const nodes: DiagramNode[] = usages.map((u) => {
    const def = defs.get(u.type.split("::").pop() ?? u.type);
    return { id: u.name, label: u.name, type: u.type, bought: boughtDefs.has(def?.name ?? ""), ports: def?.ports ?? [], x: 0, y: 0 };
  });
  const edges: DiagramEdge[] = module.sysml.connections
    .filter((c) => !assemblyName || c.owner.endsWith(assemblyName))
    .map((c, i) => {
      const [source, sourcePort] = split(c.a);
      const [target, targetPort] = split(c.b);
      const port = defs.get(nodes.find((n) => n.id === source)?.type.split("::").pop() ?? "")?.ports.find((p) => p.name === sourcePort);
      return { id: `e${i}`, source, sourcePort, target, targetPort, label: port?.type.replace(/Interface_v\d+$/, "") ?? "" };
    })
    .filter((e) => nodes.some((n) => n.id === e.source) && nodes.some((n) => n.id === e.target));
  layout(nodes, edges);
  return { nodes, edges };
}

function split(end: string): [string, string] {
  const i = end.lastIndexOf(".");
  return i < 0 ? [end, ""] : [end.slice(0, i), end.slice(i + 1)];
}

function layout(nodes: DiagramNode[], edges: DiagramEdge[]) {
  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: "LR", nodesep: 40, ranksep: 90 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of nodes) g.setNode(n.id, { width: 180, height: 40 + 18 * Math.max(1, n.ports.length) });
  for (const e of edges) g.setEdge(e.source, e.target);
  dagre.layout(g);
  for (const n of nodes) {
    const pos = g.node(n.id);
    n.x = pos.x - 90;
    n.y = pos.y - (40 + 18 * Math.max(1, n.ports.length)) / 2;
  }
}
