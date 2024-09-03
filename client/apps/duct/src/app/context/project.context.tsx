import { Project } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';
import { environment } from '../../environments/environment';

interface IProjectContext {
  project: Project | undefined;
  setProject: Dispatch<SetStateAction<Project | undefined>>;
}
const projectContext = createContext<IProjectContext | undefined>(undefined);
projectContext.displayName = 'ProjectContext';

export function useProject() {
  return useContext(projectContext);
}

export function ProvideProject({ children }: RouteProps) {
  const project = useProvideProject();
  return (
    <projectContext.Provider value={project}>
      {children}
    </projectContext.Provider>
  );
}

function useProvideProject() {
  // check if project is saved in session
  const sessionProject = sessionStorage.getItem(
    environment.PROJECT_SESSION_KEY
  );
  const sessionProjectObj = sessionProject
    ? (JSON.parse(sessionProject) as Project)
    : undefined;

  const [project, setProject] = useState<Project | undefined>(
    sessionProjectObj
  );

  return {
    project,
    setProject,
  };
}
