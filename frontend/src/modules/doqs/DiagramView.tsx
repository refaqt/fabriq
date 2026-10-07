import { useMemo } from "react";
import { Background, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import type { Module } from "../../app/api";
import { diagramOf, type DiagramNode } from "./diagram";

function PartNode({ data }: NodeProps<Node<DiagramNode>>) {
  const d = data;
  return (
    <div className={`rounded-[var(--radius)] border bg-card px-3 py-2 text-xs shadow ${d.bought ? "border-warning/60" : "border-primary/60"}`} style={{ width: 180 }}>
      <div className="font-semibold">{d.label}</div>
      <div className="text-[10px] text-muted-foreground">{d.type}{d.bought ? " · bought" : ""}</div>
      {d.ports.map((p, i) => (
        <div key={p.name} className="relative mt-1 flex items-center justify-between text-[10px]">
          <span>{p.conjugated ? "~" : ""}{p.name}</span>
          <Handle type={p.conjugated ? "target" : "source"} position={p.conjugated ? Position.Left : Position.Right} id={p.name}
            style={{ top: 44 + i * 18, background: p.conjugated ? "hsl(var(--warning))" : "hsl(var(--primary))" }} />
        </div>
      ))}
    </div>
  );
}

const nodeTypes = { part: PartNode };

export function DiagramView({ module }: { module: Module }) {
  const { nodes, edges } = useMemo(() => {
    const d = diagramOf(module);
    const nodes: Node<DiagramNode>[] = d.nodes.map((n) => ({ id: n.id, type: "part", position: { x: n.x, y: n.y }, data: n }));
    const edges: Edge[] = d.edges.map((e) => ({
      id: e.id, source: e.source, sourceHandle: e.sourcePort, target: e.target, targetHandle: e.targetPort, label: e.label,
      style: { stroke: "hsl(var(--primary))" }, labelStyle: { fill: "hsl(var(--muted-foreground))", fontSize: 10 }, labelBgStyle: { fill: "hsl(var(--card))" },
    }));
    return { nodes, edges };
  }, [module]);
  if (nodes.length === 0) return <p className="text-sm text-muted-foreground">No part usages in the SysML yet. Add parts with "scaffold part" or "use part".</p>;
  return (
    <div className="h-[28rem] rounded-[var(--radius)] border">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView nodesDraggable nodesConnectable={false} proOptions={{ hideAttribution: true }}>
        <Background color="hsl(var(--border))" gap={20} />
      </ReactFlow>
    </div>
  );
}
