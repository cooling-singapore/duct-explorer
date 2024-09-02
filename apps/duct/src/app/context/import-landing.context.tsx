import { ImportLandingContext } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

interface IImportLandingContext {
  context: ImportLandingContext;
  setContext: Dispatch<SetStateAction<ImportLandingContext>>;
}
const importLandingContext = createContext<IImportLandingContext | undefined>(
  undefined
);
importLandingContext.displayName = 'ImportLandingContext';

export function useImportLanding() {
  const context = useContext(importLandingContext);
  if (context === undefined) {
    throw new Error(
      'useImportLanding must be used within ProvideImportLandingContextContext'
    );
  }
  return context;
}

export function ProvideImportLandingContextContext({ children }: RouteProps) {
  const context = useProvideImportLandingContextContext();
  return (
    <importLandingContext.Provider value={context}>
      {children}
    </importLandingContext.Provider>
  );
}

function useProvideImportLandingContextContext() {
  const [context, setContext] = useState<ImportLandingContext>({
    selectedImportId: undefined,
  });

  return {
    context,
    setContext,
  };
}
