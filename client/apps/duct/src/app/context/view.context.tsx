import { ViewContext } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

interface IViewContext {
  context: ViewContext;
  setContext: Dispatch<SetStateAction<ViewContext>>;
}
const viewContext = createContext<IViewContext | undefined>(undefined);
viewContext.displayName = 'ViewContext';

export function useView() {
  const context = useContext(viewContext);
  if (context === undefined) {
    throw new Error('useView must be used within ProvideViewContext');
  }
  return context;
}

export function ProvideViewContext({ children }: RouteProps) {
  const context = useProvideViewContext();
  return (
    <viewContext.Provider value={context}>{children}</viewContext.Provider>
  );
}

function useProvideViewContext() {
  const [context, setContext] = useState<ViewContext>({
    view: undefined,
  });

  return {
    context,
    setContext,
  };
}
