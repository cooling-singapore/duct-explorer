import { ChartData } from 'chart.js';
import { Pie } from 'react-chartjs-2';
import { Chart as ChartJS, ArcElement, Tooltip, Legend, Title } from 'chart.js';

ChartJS.register(ArcElement, Tooltip, Legend, Title);

interface PieChartProps {
  data: ChartData<'pie'>;
  options: object;
}

function PieChart(props: PieChartProps) {
  const { data, options } = props;
  return <Pie options={options} data={data} />;
}

export default PieChart;
