import { SceneContext, SceneType } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

interface ISceneContext {
  context: SceneContext;
  setContext: Dispatch<SetStateAction<SceneContext>>;
}
const sceneContext = createContext<ISceneContext | undefined>(undefined);
sceneContext.displayName = 'SceneContext';

export function useScene() {
  const context = useContext(sceneContext);
  if (context === undefined) {
    throw new Error('useScene must be used within ProvideSceneContext');
  }
  return context;
}

export function ProvideSceneContext({ children }: RouteProps) {
  const context = useProvideSceneContext();
  return (
    <sceneContext.Provider value={context}>{children}</sceneContext.Provider>
  );
}

function useProvideSceneContext() {
  const [context, setContext] = useState<SceneContext>({
    sceneType: SceneType.Islandwide,
    zoneVersions: [],
    module_settings: {},
    errors: new Set(),
  });

  return {
    context,
    setContext,
  };
}
