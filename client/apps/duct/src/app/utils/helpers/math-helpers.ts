import { vec3 } from 'gl-matrix';
import Proj4 from 'proj4';

export function isPowerOf2(value: number) {
  return (value & (value - 1)) === 0;
}

// const magicNumberX = 20037508.34;
// const magicNumberY = 20037508.34;
// reference https://gist.github.com/onderaltintas/6649521
export function degree2meter(lon: number, lat: number) {
  // const x = (lon * magicNumberX) / 180;
  // let y = Math.log(Math.tan(((90 + lat) * Math.PI) / 360)) / (Math.PI / 180);
  // y = (y * magicNumberY) / 180;
  // return [x, y];
  return Proj4('EPSG:4326', 'EPSG:3857', [lon, lat]);
}

export function meter2degree(x: number, y: number) {
  // const lon = (x * 180) / magicNumberX;
  // const lat =
  //   (Math.atan(Math.exp((y * Math.PI) / magicNumberY)) * 360) / Math.PI - 90;
  // return [lon, lat];
  return Proj4('EPSG:3857', 'EPSG:4326', [x, y]);
}

export function precision(origin: number[], matrix: number[]) {
  matrix[12] -= origin[0];
  matrix[13] -= origin[1];
  matrix[14] -= origin[2];
}

function solvingQuadratics(
  a: number,
  b: number,
  c: number
): undefined | number[] {
  const result: number[] = [];
  const delta = b * b - 4.0 * a * c;
  if (delta < 0) {
    return undefined;
  }

  if (Math.abs(delta) < 0.00000001) {
    result.push(-b / (2 * a));
  } else {
    result.push((-b + Math.sqrt(delta)) / (2 * a));
    result.push((-b - Math.sqrt(delta)) / (2 * a));
  }

  return result;
}

export function lineSphereIntersect(
  startPoint: number[],
  endPoint: number[],
  sphereCenter: number[],
  sphereRadius: number
): undefined | Float32Array[] {
  const startPointVec = new Float32Array(startPoint);
  const endPointVec = new Float32Array(endPoint);
  const sphereCenterVec = new Float32Array(sphereCenter);

  const directionVec = new Float32Array(3);
  vec3.subtract(directionVec, endPointVec, startPointVec);

  const a =
    directionVec[0] * directionVec[0] +
    directionVec[1] * directionVec[1] +
    directionVec[2] * directionVec[2];
  const b =
    2 * directionVec[0] * (startPointVec[0] - sphereCenterVec[0]) +
    2 * directionVec[1] * (startPointVec[1] - sphereCenterVec[1]) +
    2 * directionVec[2] * (startPointVec[2] - sphereCenterVec[2]);
  const c =
    (startPointVec[0] - sphereCenterVec[0]) *
      (startPointVec[0] - sphereCenterVec[0]) +
    (startPointVec[1] - sphereCenterVec[1]) *
      (startPointVec[1] - sphereCenterVec[1]) +
    (startPointVec[2] - sphereCenterVec[2]) *
      (startPointVec[2] - sphereCenterVec[2]) -
    sphereRadius * sphereRadius;

  const scalars = solvingQuadratics(a, b, c);

  if (scalars === undefined) {
    return undefined;
  } else {
    const points = [];
    const tempVec = new Float32Array(3);
    for (let i = 0; i < scalars.length; i++) {
      if (scalars[i] >= 0 && scalars[i] <= 1) {
        vec3.scale(tempVec, directionVec, scalars[i]);
        vec3.add(tempVec, tempVec, startPointVec);
        points.push(tempVec);
      }
    }
    if (points.length > 0) {
      return points;
    } else {
      return undefined;
    }
  }
}
