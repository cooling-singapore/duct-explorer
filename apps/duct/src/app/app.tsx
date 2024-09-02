import { lazy, Suspense, useEffect, useMemo } from 'react';
import { Routes, Route, useNavigate, Navigate, Outlet } from 'react-router-dom';
import FolderIcon from '@mui/icons-material/Folder';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import BarChartIcon from '@mui/icons-material/BarChart';
import AssignmentTurnedInIcon from '@mui/icons-material/AssignmentTurnedIn';
import SettingsIcon from '@mui/icons-material/Settings';
import FlipIcon from '@mui/icons-material/Flip';
import CreateIcon from '@mui/icons-material/Create';
import UploadIcon from '@mui/icons-material/Upload';

import { AppLayout2, LoadingIndicator } from '@duct-core/ui';
import { PrivateRoute, useAuth } from './context/auth.context';
import { SideBarMenuItem, SideBarSettingItem } from '@duct-core/data';
import { useProject } from './context/project.context';
import { ProvideBuildContext } from './context/build.context';
import { environment } from '../environments/environment';

const CreateSceneLanding = lazy(() => import('./build/create-scene/create-scene-landing'));

const ImportWorkflowLanding = lazy(
  () => import('./import/import-workflow/import-workflow-landing')
);
const ImportLanding = lazy(() => import('./import/import-landing'));
const Profile = lazy(() => import('./settings/profile/profile'));
const ProjectList = lazy(() => import('./settings/project/project-list'));
const SettingsShell = lazy(() => import('./settings/settings-shell'));

const CompareLanding = lazy(() => import('./compare/compare-landing'));
const Signin = lazy(() => import('./signin/signin'));
const AnalyseLanding = lazy(
  () => import('./analyse/analyse-landing/analyse-landing')
);
const BuildLanding = lazy(() => import('./build/build-landing/build-landing'));
const ReviewLanding = lazy(
  () => import('./review/review-landing/review-landing')
);

const AnalysisConfigList = lazy(
  () => import('./manage/analysis-config-list/analysis-config-list')
);

const ProjectCreation = lazy(
  () => import('./settings/project/project-creation/project-creation')
);

export function App() {
  const navigate = useNavigate();
  const auth = useAuth();
  const projectContext = useProject();

  useEffect(() => {
    if (!projectContext?.project) {
      //if no project is selected; redirect to project selection
      navigate('/manage/projects');
    }
  }, [projectContext]);

  const onProjectClick = () => {
    // clear project from context
    projectContext?.setProject(undefined);
    // clear project from session
    sessionStorage.removeItem(environment.PROJECT_SESSION_KEY);
  };

  const settingsItems: SideBarSettingItem[] = useMemo(
    () => [
      {
        icon: <FolderIcon color="primary" />,
        text: 'Projects',
        key: 'project',
        next: onProjectClick,
      },
      {
        icon: <ExitToAppIcon color="primary" />,
        text: 'Signout',
        key: 'signout',
        next: () => {
          projectContext?.setProject(undefined);
          auth?.signout(() => navigate('/login'));
        },
      },
    ],
    []
  );

  const menuItems: SideBarMenuItem[] = useMemo(
    () => [
      {
        icon: <UploadIcon />,
        text: 'Import',
        key: 'import',
        route: `import`,
      },
      {
        icon: <CreateIcon />,
        text: 'Build',
        key: 'build',
        route: `build`,
      },
      {
        icon: <BarChartIcon />,
        text: 'Analyse',
        key: 'analyse',
        route: `analyse`,
      },
      {
        icon: <SettingsIcon />,
        text: 'Manage',
        key: 'manage',
        route: `manage`,
      },
      {
        icon: <AssignmentTurnedInIcon />,
        text: 'Review',
        key: 'review',
        route: `review`,
      },
      {
        icon: <FlipIcon />,
        text: 'Compare',
        key: 'compare',
        route: `compare`,
      },
    ],
    []
  );

  return (
    <Suspense fallback={<LoadingIndicator loading />}>
      <Routes>
        <Route path="/login" element={<Signin />} />
        <Route
          path="/app"
          element={
            <PrivateRoute
              children={
                <AppLayout2
                  menuItems={menuItems}
                  appTitle={environment.APP_TITLE}
                  settingItems={settingsItems}
                  logoPath={environment.APP_LOGO}
                  projectName={projectContext?.project?.name || ''}
                >
                  <Outlet />
                </AppLayout2>
              }
            />
          }
        >
          <Route path={``} element={<Navigate to="build" />} />
          <Route path={`*`} element={<Navigate to="build" />} />
          <Route path={`import/*`} element={<Import />} />
          <Route path={`build/*`} element={<Build />} />
          <Route path={`analyse/*`} element={<Analyse />} />
          <Route path={`manage/*`} element={<Manage />} />
          <Route path={`review/*`} element={<Review />} />
          <Route path={`compare/*`} element={<Compare />} />
        </Route>
        <Route
          path="/manage"
          element={
            <PrivateRoute
              children={
                <SettingsShell>
                  <Outlet />
                </SettingsShell>
              }
            />
          }
        >
          <Route path={``} element={<Navigate to="projects" />} />
          <Route path={`*`} element={<Navigate to="projects" />} />
          <Route path={`projects`} element={<ProjectList />} />
          <Route path={`create-project`} element={<ProjectCreation />} />
          <Route path={`profile`} element={<Profile />} />
        </Route>
        <Route path={`/`} element={<Navigate to="/manage" />} />
        <Route path={`*`} element={<Navigate to="/manage" />} />
      </Routes>
    </Suspense>
  );
}

function Compare() {
  return (
    <Routes>
      <Route index element={<CompareLanding />} />
    </Routes>
  );
}

function Review() {
  return (
    <Routes>
      <Route index element={<ReviewLanding />} />
    </Routes>
  );
}

function Import() {
  return (
    <Routes>
      <Route>
        <Route path={`workflow`} element={<ImportWorkflowLanding />} />
        <Route index element={<ImportLanding />} />
      </Route>
    </Routes>
  );
}

function Build() {
  return (
    <ProvideBuildContext>
      <Routes>
        <Route path={`workflow`} element={<CreateSceneLanding />} />
        <Route index element={<BuildLanding />} />
      </Routes>
    </ProvideBuildContext>
  );
}

function Analyse() {
  return (
    <Routes>
      <Route index element={<AnalyseLanding />} />
    </Routes>
  );
}

function Manage() {
  return (
    <Routes>
      <Route index element={<AnalysisConfigList />} />
    </Routes>
  );
}

export default App;
