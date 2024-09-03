import { AnalyseForm } from '@duct-core/data';
import { Box } from '@mui/material';
import { IChangeEvent } from '@rjsf/core';
import { Form } from '@rjsf/mui';
import validator from '@rjsf/validator-ajv8';
import { useFormContext } from 'react-hook-form';

import { useProject } from '../../../context/project.context';
import MarkdownField from '../../../utils/ui/custom-form-widgets/markdown-field';
import RangeWidget from '../../../utils/ui/custom-form-widgets/range-widget';
import UploadValidatorWidget from '../../../utils/ui/custom-form-widgets/upload-validator-widget';
import CostEstimate from '../cost-estimate/cost-estimate';
import AnalysisInfo from './analysis-info';
import AnalysisSelect from './form-components/analysis-select';

// 279: Support for custom wind potential filter fields
const customWidgets = {
  uploadValidator: UploadValidatorWidget,
  markdown: MarkdownField,
  rangeWidget: RangeWidget,
};

const AnalyseStep2 = () => {
  const { watch, setValue } = useFormContext<AnalyseForm>();

  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  const analysis = watch('analysis');
  const analysisForm = watch('analysisForm');
  const aoi_obj_id = watch('aoi_obj_id');
  const scene = watch('scene');

  const formUpdated = (form: IChangeEvent) => {
    setValue('analysisForm', form.formData);
  };

  return (
    <Box my={2}>
      <AnalysisSelect />

      {analysis && (
        <>
          <Box>
            <AnalysisInfo
              contributors={analysis.further_information}
              description={analysis.description}
              image={analysis.sample_image}
            />
            <Form
              schema={analysis.parameters_schema}
              uiSchema={analysis.ui_schema}
              liveValidate
              showErrorList={false}
              onChange={formUpdated}
              formData={analysisForm}
              widgets={customWidgets}
              validator={validator}
            >
              {/* Empty fragment allows us to remove the submit button from the rjsf form */}
              {/*  eslint-disable-next-line react/jsx-no-useless-fragment */}
              <></>
            </Form>
          </Box>
          <Box>
            <CostEstimate
              projectId={projectId}
              sceneId={scene.id}
              parameters={analysisForm}
              sceneName={scene.name}
              aoiId={aoi_obj_id}
              analysisType={analysis.name}
              onError={(isvalid: boolean) => {
                // update form validty
                // dispatch({
                //   type: WorkflowActionKind.SET_FORM_VALID,
                //   payload: {
                //     isFormValid: !shouldDisableSubmit() && !isvalid,
                //   },
                // });
              }}
            />
          </Box>
        </>
      )}
    </Box>
  );
};

export default AnalyseStep2;
