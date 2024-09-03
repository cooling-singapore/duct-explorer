import { ChartConfiguration, ChartData, Point } from 'chart.js';
import {
  BarWithErrorBarsController,
  BarWithErrorBar,
} from 'chartjs-chart-error-bars';
import {
  Chart as ChartJS,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Title,
} from 'chart.js';
import { Scatter } from 'react-chartjs-2';

ChartJS.register(
  PointElement,
  LineElement,
  LinearScale,
  BarWithErrorBarsController,
  BarWithErrorBar,
  Title,
  Tooltip,
  Legend
);

interface ScatterChartProps {
  data: ChartData<'scatter', (number | Point | null)[], unknown>;
  options: object;
}
function ScatterChart(props: ScatterChartProps) {
  const { data, options } = props;
  return <Scatter options={options} data={data} />;
}

export default ScatterChart;
