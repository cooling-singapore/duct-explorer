import { Box } from '@mui/material';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Legend,
  Tooltip,
} from 'chart.js';
import { Bar } from 'react-chartjs-2';
import { useMutation } from 'react-query';
import { useEffect, useState } from 'react';
import { FieldProps } from '@rjsf/utils';

import { DemandChartProps, getModuleChart } from '@duct-core/data';
import { useProject } from '../../../context/project.context';
import { useScene } from '../../../context/scene.context';

ChartJS.register(CategoryScale, LinearScale, BarElement, Tooltip, Legend);

function DemandChart(props: FieldProps) {
  const schema = props.uiSchema as DemandChartProps;
  const projectContext = useProject();
  const sceneContext = useScene();
  const [data, setdata] = useState<object | undefined>(undefined);
  const powerPlantsPayload =
    sceneContext.context.module_settings[schema.module_name];

  const barOptions = {
    maintainAspectRatio: false,
    indexAxis: 'y' as const, //horizontal bar
    responsive: true,
    plugins: {
      legend: {
        position: 'bottom' as const,
        align: 'start' as const,
      },
      //   datalabels: {
      //     color: '#ffffff',
      //     clip: true,
      //     display: 'auto',
      //     // offset: 5,
      //     anchor: 'start' as const,
      //     align: 'start' as const,
      //   },
    },
    scales: {
      x: {
        stacked: true,
        display: false,
      },
      y: {
        stacked: true,
      },
    },
  };

  const getModuleVisualizationMutation = useMutation((moduleName: string) =>
    getModuleChart(
      projectContext?.project?.id || '',
      moduleName,
      sceneContext.context
    ).then(setdata)
  );

  useEffect(() => {
    if (powerPlantsPayload) {
      getModuleVisualizationMutation.mutate(schema.module_name);
    }
  }, [powerPlantsPayload]);

  if (data) {
    return (
      <Box height={220}>
        <Bar options={barOptions} data={data as any} />
      </Box>
    );
  } else {
    return null;
  }
}

export default DemandChart;
