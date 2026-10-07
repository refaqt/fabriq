import { describe, expect, it } from "vitest";
import { diagramOf } from "./diagram";
import type { Module } from "../../app/api";

const module = {
  slug: "modules/stage", name: "Stage", version: "0.1.0", function: "", provides: [], consumes: [], components: [],
  parts: [], bought: [{ bom: "MEC-001", part: "stoq:hiwin/hgr-rail#X", sysml: "GuideRail" }], bom: [], params: [], role: null, problems: [],
  sysml: {
    files: ["stage.sysml"], interfaces: [], requirements: [],
    parts: [
      { name: "Base", doc: null, ports: [{ name: "railMount", type: "RailMountInterface_v1", conjugated: false }], usages: [], connections: [] },
      { name: "GuideRail", doc: null, ports: [{ name: "baseMount", type: "RailMountInterface_v1", conjugated: true }], usages: [], connections: [] },
      { name: "Stage", doc: null, ports: [], usages: [{ name: "base", type: "Base" }, { name: "rail", type: "GuideRail" }], connections: [] },
    ],
    connections: [{ owner: "Stage::Stage", a: "base.railMount", b: "rail.baseMount" }],
  },
} as unknown as Module;

describe("diagramOf", () => {
  it("makes a node per usage and an edge per connect, laid out left to right", () => {
    const { nodes, edges } = diagramOf(module);
    expect(nodes.map((n) => n.id)).toEqual(["base", "rail"]);
    expect(nodes[1].bought).toBe(true);
    expect(nodes[0].ports[0].name).toBe("railMount");
    expect(edges).toHaveLength(1);
    expect(edges[0]).toMatchObject({ source: "base", sourcePort: "railMount", target: "rail", targetPort: "baseMount", label: "RailMount" });
    expect(nodes[1].x).toBeGreaterThan(nodes[0].x);
  });
});
