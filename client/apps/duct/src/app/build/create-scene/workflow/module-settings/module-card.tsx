import {
  Card,
  CardContent,
  Stack,
  Typography,
  CardActions,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Box,
  CircularProgress,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useState } from 'react';
import { Form } from '@rjsf/mui';
import { IChangeEvent } from '@rjsf/core';
import validator from '@rjsf/validator-ajv8';
import { RegistryWidgetsType } from '@rjsf/utils';

import { SceneModule } from '@duct-core/data';
import { useScene } from '../../../../context/scene.context';
import MultiSlider from '../../../../utils/ui/custom-form-widgets/multi-slider';
import DemandChart from '../../../../utils/ui/custom-form-widgets/demand-chart';
import HeatEmission from '../../../../utils/ui/custom-form-widgets/heat-emission';
import RangeWidget from '../../../../utils/ui/custom-form-widgets/range-widget';
import RadioWidget from '../../../../utils/ui/custom-form-widgets/radio-widget';
import UploadWidget from '../../../../utils/ui/custom-form-widgets/upload-widget';

interface ModuleCardProps {
  data: SceneModule;
  active: boolean;
  onClick: (activeModule: SceneModule) => void;
  loading: boolean;
}

function ModuleCard(props: ModuleCardProps) {
  const { data, active, onClick, loading } = props;
  const sceneContext = useScene();

  const [formData, setFormData] = useState<object | undefined>(
    sceneContext.context.module_settings[data.name]
  );

  const customField = {
    multislider: MultiSlider,
    demandChart: DemandChart,
    heatEmission: HeatEmission,
  };

  const formUpdated = (form: IChangeEvent) => {
    setFormData(form.formData);
    updateContextFormData(form.formData);
  };

  const updateContextFormData = (formData: object | undefined) => {
    sceneContext.setContext((prevState) => {
      const copy = { ...prevState };
      const prevSettings = copy.module_settings[data.name];
      copy.module_settings[data.name] = { ...prevSettings, ...formData };
      return copy;
    });
  };

  const onCardClick = () => {
    if (!active) {
      onClick(data);
    }
  };

  const widgets: RegistryWidgetsType = {
    rangeWidget: RangeWidget,
    radioDescWidget: RadioWidget,
    uploadWidget: UploadWidget,
  };

  return (
    <Card
      sx={{
        cursor: 'pointer',
        minWidth: 275,
        ...(active && {
          bgcolor: 'info.light',
          border: '2px solid',
          borderColor: 'info.main',
        }),
      }}
      onClick={onCardClick}
    >
      <CardContent>
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 2 }}>
          <img
            style={{ width: '25px' }}
            src={`./assets/icons/${data.icon}`}
            alt="module-icon"
          />
          <Typography>{data.label}</Typography>
        </Stack>
        <Typography
          variant="body2"
          dangerouslySetInnerHTML={{
            __html: data.description,
          }}
        />
        {loading && (
          <Stack mt={2} spacing={1} direction="row">
            <CircularProgress size={15} />
            <Typography variant="caption">Creating preview</Typography>
          </Stack>
        )}
      </CardContent>
      {!data.hide_settings_accordion && (
        <CardActions>
          <Accordion sx={{ maxWidth: '100%', minWidth: '100%' }}>
            <AccordionSummary
              expandIcon={<ExpandMoreIcon />}
              aria-controls="panel1a-content"
              id="panel1a-header"
            >
              <Typography>Edit Settings</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ mt: -4 }}>
              {data.settings_description && (
                <Box my={2}>
                  <Typography
                    variant="body2"
                    dangerouslySetInnerHTML={{
                      __html: data.settings_description,
                    }}
                  />
                </Box>
              )}

              {data.settings_image && (
                <Box>
                  <img
                    style={{ width: '100%' }}
                    src={`./assets/moduleImages/${data.settings_image}`}
                    alt="module setting desc"
                  />
                </Box>
              )}
              <Form
                schema={data.parameters_schema}
                uiSchema={data.ui_schema}
                formData={formData}
                onChange={formUpdated}
                validator={validator}
                fields={customField}
                widgets={widgets}
                omitExtraData
                liveOmit
              >
                <></>
              </Form>
            </AccordionDetails>
          </Accordion>
        </CardActions>
      )}
    </Card>
  );
}

export default ModuleCard;
