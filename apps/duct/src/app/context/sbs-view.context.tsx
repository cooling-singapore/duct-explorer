import { SBSViewContext } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

interface IViewContext {
  context: SBSViewContext;
  setContext: Dispatch<SetStateAction<SBSViewContext>>;
}
const viewContext = createContext<IViewContext | undefined>(undefined);
viewContext.displayName = 'SBSViewContext';

export function useSBSView() {
  return useContext(viewContext);
}

export function ProvideSBSViewContext({ children }: RouteProps) {
  const context = useProvideSBSViewContext();
  return (
    <viewContext.Provider value={context}>{children}</viewContext.Provider>
  );
}

function useProvideSBSViewContext() {
  const [context, setContext] = useState<SBSViewContext>({
    leftView: undefined,
    rightView: undefined,
  });

  return {
    context,
    setContext,
  };
}
