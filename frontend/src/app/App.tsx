import { Route, Routes } from "react-router-dom";
import { Shell } from "./Shell";
import { doqsRoutes } from "../modules/doqs";

/** The shell plus every module's routes. A later module adds its own list here. */
export function App() {
  return (
    <Shell>
      <Routes>
        {doqsRoutes.map((r) => <Route key={r.path} path={r.path} element={r.element} />)}
      </Routes>
    </Shell>
  );
}
