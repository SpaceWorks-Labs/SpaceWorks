import { useEffect, useRef, useState } from "react";
import { ActionControl } from "../../../components/ui";
import type { PreviewMesh } from "./types";

/** Render only checked numeric mesh buffers; textures/material URLs never cross. */
export default function MeshCanvas({ meshes }: { meshes: PreviewMesh[] }) {
  const host = useRef<HTMLDivElement>(null);
  const turn = useRef<(angle: number) => void>(() => {});
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let disposed = false;
    let cleanup = () => {};
    void Promise.all([import("three"), import("three/addons/controls/OrbitControls.js")]).then(([T, { OrbitControls }]) => {
      if (disposed || !host.current) return;
      const element = host.current;
      const color = (token: string) => {
        const channels = getComputedStyle(element).getPropertyValue(token).trim().split(/\s+/).map(Number);
        if (channels.length !== 3 || channels.some(n => !Number.isFinite(n) || n < 0 || n > 255)) throw new Error("Theme unavailable.");
        return `rgb(${channels.join(",")})`;
      };
      const renderer = new T.WebGLRenderer({ antialias: true });
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      renderer.setClearColor(color("--color-panel"));
      element.append(renderer.domElement);
      const scene = new T.Scene(), group = new T.Group(); scene.add(group);
      const material = new T.MeshStandardMaterial({ color: color("--color-brand-boundary"), roughness: .8 });
      const geometries = meshes.map(mesh => {
        const geometry = new T.BufferGeometry();
        geometry.setAttribute("position", new T.BufferAttribute(mesh.positions, 3)); geometry.computeVertexNormals();
        group.add(new T.Mesh(geometry, material)); return geometry;
      });
      const box = new T.Box3().setFromObject(group), center = box.getCenter(new T.Vector3());
      group.position.sub(center);
      const span = Math.max(box.getSize(new T.Vector3()).length(), .001);
      const camera = new T.PerspectiveCamera(45, 1, span / 1000, span * 100);
      camera.position.set(span, span, span);
      const light = new T.HemisphereLight(color("--color-panel"), color("--color-bg"), 3); scene.add(light);
      const controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = false;
      const render = () => renderer.render(scene, camera);
      const resize = () => {
        const width = Math.max(1, element.clientWidth); renderer.setSize(width, 320);
        camera.aspect = width / 320; camera.updateProjectionMatrix(); render();
      };
      controls.addEventListener("change", render); controls.update();
      turn.current = angle => { group.rotation.y += angle; render(); };
      const observer = new ResizeObserver(resize); observer.observe(element); resize();
      const theme = new MutationObserver(() => {
        renderer.setClearColor(color("--color-panel")); material.color.set(color("--color-brand-boundary"));
        light.color.set(color("--color-panel")); light.groundColor.set(color("--color-bg")); render();
      });
      theme.observe(document.documentElement, { attributes: true, attributeFilter: ["class", "style", "data-theme"] });
      cleanup = () => { observer.disconnect(); theme.disconnect(); controls.dispose(); geometries.forEach((g: { dispose: () => void }) => g.dispose());
        material.dispose(); renderer.dispose(); renderer.domElement.remove(); };
    }).catch(() => setFailed(true));
    return () => { disposed = true; cleanup(); };
  }, [meshes]);
  if (failed) return <p role="status">This device cannot display the model. Download the original to view it.</p>;
  return <div className="grid gap-3">
    <div ref={host} className="min-h-80 overflow-hidden rounded-xl border border-line bg-panel" role="img" aria-label="Project model preview" />
    <div className="flex gap-3"><ActionControl action={{ label: "Rotate left", onClick: () => turn.current(-Math.PI / 8) }} />
      <ActionControl action={{ label: "Rotate right", onClick: () => turn.current(Math.PI / 8) }} /></div>
  </div>;
}
