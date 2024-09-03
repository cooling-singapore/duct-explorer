export interface TimeFilterSchema {
  at: Bucket[];
  rh: Bucket[];
  wd: Bucket[];
  ws: Bucket[];
}

export interface Bucket {
  value: number;
  timestamps: number[];
}

export interface SliderMark {
  value: number;
  label: string;
}

export interface BarDatum {
  x: string;
  y: number;
}

export interface AxisRange {
  ymin: number;
  ymax: number;
  xmin: number;
  xmax: number;
}
