import { HomePage } from "./HomePage";
import { ModulesPage } from "./ModulesPage";
import { ModulePage } from "./ModulePage";
import { LibraryPage } from "./LibraryPage";
import { AddPartWizard } from "./AddPartWizard";
import { GitPage } from "./GitPage";

export const doqsRoutes = [
  { path: "/", element: <HomePage /> },
  { path: "/modules", element: <ModulesPage /> },
  { path: "/modules/*", element: <ModulePage /> },
  { path: "/library", element: <LibraryPage /> },
  { path: "/library/add", element: <AddPartWizard /> },
  { path: "/git", element: <GitPage /> },
];
