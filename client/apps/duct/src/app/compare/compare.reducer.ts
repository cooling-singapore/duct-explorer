import {
  AnalysisScale,
  CompareActionKind,
  ResultCompareState,
} from '@duct-core/data';

export const resultCompareReducer = (
  state: ResultCompareState,
  action: { type: CompareActionKind; payload: Partial<ResultCompareState> }
): ResultCompareState => {
  const { type, payload } = action;
  switch (type) {
    case CompareActionKind.SET_SELECTED_ANALYSIS:
      return {
        ...state,
        selectedAnalysis: payload.selectedAnalysis,
        analysisRuns: payload.analysisRuns,
        rightRun: undefined,
        leftRun: undefined,
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        paramForm: {},
        formComplete: false,
        selectedResult: undefined,
        panelResults: undefined,
      };
    case CompareActionKind.SET_LEFT_RUN:
      return {
        ...state,
        leftRun: payload.leftRun,
        rightRunList: payload.rightRunList,
        rightRun: undefined,
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        paramForm: {},
        formComplete: false,
        selectedResult: undefined,
        panelResults: undefined,
      };
    case CompareActionKind.SET_RIGHT_RUN:
      return {
        ...state,
        rightRun: payload.rightRun,
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        paramForm: {},
        formComplete: false,
        selectedResult: undefined,
        panelResults: undefined,
      };
    case CompareActionKind.SET_RESULT:
      return {
        ...state,
        leftResult: payload.leftResult,
        rightResult: payload.rightResult,
        panelResults: payload.panelResults,
      };
    case CompareActionKind.SET_COMPARE_MODE:
      return {
        ...state,
        isDeltaCompare: payload.isDeltaCompare,
      };
    case CompareActionKind.SET_DELTA_RESULT:
      return {
        ...state,
        deltaResult: payload.deltaResult,
        panelResults: payload.panelResults,
      };
    case CompareActionKind.SET_FORM:
      return {
        ...state,
        paramForm: payload.paramForm || {},
        formComplete: payload.formComplete,
      };
    case CompareActionKind.SET_FORM_COMPLETED:
      return {
        ...state,
        formComplete: payload.formComplete,
        paramForm: payload.paramForm || {},
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        panelResults: undefined,
      };
    case CompareActionKind.SET_SELECTED_RESULT:
      return {
        ...state,
        selectedResult: payload.selectedResult,
        paramForm: {},
        formComplete: payload.formComplete,
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        panelResults: undefined,
      };
    case CompareActionKind.SET_PANEL_RESULT:
      return {
        ...state,
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        panelResults: payload.panelResults,
      };
    case CompareActionKind.SET_SCALE:
      return {
        ...state,
        scale: payload.scale || AnalysisScale.MESO,
        selectedAnalysis: undefined,
        rightRun: undefined,
        leftRun: undefined,
        leftResult: undefined,
        rightResult: undefined,
        deltaResult: undefined,
        paramForm: {},
        formComplete: false,
        selectedResult: undefined,
        panelResults: undefined,
      };
    default:
      return state;
  }
};
