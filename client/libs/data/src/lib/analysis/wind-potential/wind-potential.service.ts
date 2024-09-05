import axios from 'axios';
import { TimeFilterSchema } from './wind-potential.model';

export const getTimeFilterSchema = (
  projectId: string,
  params?: URLSearchParams
): Promise<TimeFilterSchema> =>
  axios
    .get(`/mtp/${projectId}${params ? `?${params.toString()}` : ''}`)
    .then((res) => res.data);
