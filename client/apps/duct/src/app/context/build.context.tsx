import { BuildContext, SceneCreationStage } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

interface IBuildContext {
  context: BuildContext;
  setContext: Dispatch<SetStateAction<BuildContext>>;
}
const buildContext = createContext<IBuildContext | undefined>(undefined);
buildContext.displayName = 'BuildContext';

export function useBuild() {
  const context = useContext(buildContext);
  if (context === undefined) {
    throw new Error('useBuild must be used within ProvideBuildContext');
  }
  return context;
}

export function ProvideBuildContext({ children }: RouteProps) {
  const context = useProvideBuildContext();
  return (
    <buildContext.Provider value={context}>{children}</buildContext.Provider>
  );
}

function useProvideBuildContext() {
  const [context, setContext] = useState<BuildContext>({
    mapType: SceneCreationStage.Default,
    moduleVisLayers: [],
  });

  return {
    context,
    setContext,
  };
}
