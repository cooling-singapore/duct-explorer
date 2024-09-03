import { ReviewContext } from '@duct-core/data';
import {
  createContext,
  Dispatch,
  SetStateAction,
  useContext,
  useState,
} from 'react';
import { RouteProps } from 'react-router-dom';

interface IReviewContext {
  context: ReviewContext;
  setContext: Dispatch<SetStateAction<ReviewContext>>;
}
const reviewContext = createContext<IReviewContext | undefined>(undefined);
reviewContext.displayName = 'ReviewContext';

export function useReview() {
  const context = useContext(reviewContext);
  if (context === undefined) {
    throw new Error('useReview must be used within ProvideReviewContext');
  }
  return context;
}

export function ProvideReviewContext({ children }: RouteProps) {
  const context = useProvideReviewContext();
  return (
    <reviewContext.Provider value={context}>{children}</reviewContext.Provider>
  );
}

function useProvideReviewContext() {
  const [context, setContext] = useState<ReviewContext>({
    sceneId: 'default',
    showBuildingFootprint: false,
  });

  return {
    context,
    setContext,
  };
}
