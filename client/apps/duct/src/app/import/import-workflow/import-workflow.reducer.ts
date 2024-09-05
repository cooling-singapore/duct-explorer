import {
  FixMode,
  ImportWorkflowAction,
  ImportWorkflowState,
} from '@duct-core/data';

export const importWorkflowReducer = (
  state: ImportWorkflowState,
  action: { type: ImportWorkflowAction; payload: Partial<ImportWorkflowState> }
): ImportWorkflowState => {
  const { type, payload } = action;
  switch (type) {
    case ImportWorkflowAction.SET_ACTIVE_STEP:
      return {
        ...state,
        activeStep: payload.activeStep || 0,
      };
    case ImportWorkflowAction.SET_SELECTED_DATATYPE:
      return {
        ...state,
        selectedDataType: payload.selectedDataType,
      };
    case ImportWorkflowAction.SET_IMPORT_NAME:
      return {
        ...state,
        importName: payload.importName,
      };
    case ImportWorkflowAction.SET_FIX_MODE:
      return {
        ...state,
        fixMode: payload.fixMode || FixMode.PICK,
      };
    case ImportWorkflowAction.SET_LOADING:
      return {
        ...state,
        loading: !!payload.loading,
      };
    default:
      return state;
  }
};
