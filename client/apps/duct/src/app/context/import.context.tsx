import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

import {
  ImportContext,
  ImportStage,
  UploadDatasetTarget,
} from '@duct-core/data';

interface IImportContext {
  context: ImportContext;
  setContext: Dispatch<SetStateAction<ImportContext>>;
}
const importContext = createContext<IImportContext | undefined>(undefined);
importContext.displayName = 'ImportContext';

export function useImport() {
  const context = useContext(importContext);
  if (context === undefined) {
    throw new Error('useImport must be used within ProvideImportContext');
  }
  return context;
}

export function ProvideImportContext({ children }: RouteProps) {
  const context = useProvideImportContext();
  return (
    <importContext.Provider value={context}>{children}</importContext.Provider>
  );
}

function useProvideImportContext() {
  const [context, setContext] = useState<ImportContext>({
    selectedZones: undefined,
    zoneVersions: undefined,
    importStage: ImportStage.Default,
    layersToSave: {},
    currentTarget: UploadDatasetTarget.LIBRARY,
    showAreaSelection: false,
  });

  return {
    context,
    setContext,
  };
}
