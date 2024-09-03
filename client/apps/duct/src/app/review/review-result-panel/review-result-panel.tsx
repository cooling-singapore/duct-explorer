import OpenInFullIcon from '@mui/icons-material/OpenInFull';
import { Alert, Card, IconButton } from '@mui/material';
import { ReactNode, lazy, useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

import {
  PanelBarChart,
  PanelErrorBarChart,
  PanelFlowChart,
  PanelLineChart,
  PanelMarkdown,
  PanelPieChart,
  PanelScatterChart,
  PanelVisualization,
  PanelVisualizationType,
} from '@duct-core/data';
import { DialogWrapper } from '@duct-core/ui';

const FlowChart = lazy(() => import('../../utils/ui/charts_/flow-chart'));

const ScatterChart = lazy(() => import('../../utils/ui/charts_/scatter-chart'));
const ErrorBarChart = lazy(
  () => import('../../utils/ui/charts_/error-bar-chart')
);
const BarChart = lazy(() => import('../../utils/ui/charts_/bar-chart'));
const PieChart = lazy(() => import('../../utils/ui/charts_/pie-chart'));
const LineChart = lazy(() => import('../../utils/ui/charts_/line-chart'));

interface ReviewResultPanelProps {
  data: PanelVisualization[];
}

function ReviewResultPanel(props: ReviewResultPanelProps) {
  const { data } = props;
  const [expandedChart, setexpandedChart] = useState<ReactNode | undefined>(
    undefined
  );
  const [openExpandedDialog, setopenExpandedDialog] = useState(false);

  const openExpanded = (element: ReactNode) => {
    setexpandedChart(element);
    setopenExpandedDialog(true);
  };

  const panel = data.map((element, index) => {
    let chart: ReactNode = null;
    if (element.type === PanelVisualizationType.Bar) {
      const bar = element as unknown as PanelBarChart;

      chart = (
        <BarChart key={`bar-${index}`} data={bar.data} options={bar.options} />
      );
    } else if (element.type === PanelVisualizationType.Pie) {
      const pie = element as unknown as PanelPieChart;
      chart = (
        <PieChart key={`pie-${index}`} data={pie.data} options={pie.options} />
      );
    } else if (element.type === PanelVisualizationType.Line) {
      const line = element as unknown as PanelLineChart;
      chart = (
        <LineChart
          key={`line-${index}`}
          data={line.data}
          options={line.options}
        />
      );
    } else if (element.type === PanelVisualizationType.ErrorBar) {
      const bar = element as unknown as PanelErrorBarChart;
      chart = (
        <ErrorBarChart
          key={`bar-${index}`}
          data={bar.data as any}
          options={bar.options}
        />
      );
    } else if (element.type === PanelVisualizationType.FlowChart) {
      const data = element as unknown as PanelFlowChart;
      chart = <FlowChart key={`flow-chart-${index}`} data={data} />;
    } else if (element.type === PanelVisualizationType.Scatter) {
      const data = element as unknown as PanelScatterChart;
      chart = (
        <ScatterChart
          key={`scatter-chart-${index}`}
          data={data.data}
          options={data.options}
        />
      );
    } else if (element.type === PanelVisualizationType.Markdown) {
      const data = element as unknown as PanelMarkdown;
      chart = (
        <Markdown key={`markdown-${index}`} remarkPlugins={[remarkGfm]}>
          {data.data}
        </Markdown>
      );
    } else {
      chart = (
        <Alert key={`alert-${index}`} severity="warning">
          Unsupported chart type
        </Alert>
      );
    }

    return (
      <Card key={`${index}-box`} sx={{ p: 2, my: 2 }}>
        {chart}
        {element.type !== PanelVisualizationType.Markdown && (
          <IconButton title="View Expanded" onClick={() => openExpanded(chart)}>
            <OpenInFullIcon />
          </IconButton>
        )}
      </Card>
    );
  });

  return (
    <div>
      {panel.length > 0 ? panel : null}
      <DialogWrapper
        open={openExpandedDialog}
        onClose={() => setopenExpandedDialog(false)}
        children={expandedChart}
      />
    </div>
  );
}

export default ReviewResultPanel;
