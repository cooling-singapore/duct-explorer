import { ChartConfiguration } from 'chart.js';
import {
  BarWithErrorBarsController,
  BarWithErrorBar,
} from 'chartjs-chart-error-bars';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Chart } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarWithErrorBarsController,
  BarWithErrorBar,
  Title,
  Tooltip,
  Legend
);

interface ErrorBarChartProps {
  data: ChartConfiguration<'barWithErrorBars'>;
  options: object;
}
function ErrorBarChart(props: ErrorBarChartProps) {
  const { data, options } = props;
  return (
    <Chart options={options} data={data as any} type={'barWithErrorBars'} />
  );
}

export default ErrorBarChart;
