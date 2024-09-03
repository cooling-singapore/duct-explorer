import { object, string, array, boolean } from 'yup';

export interface NodeIdentity {
  e_public_key: string;
  email: string;
  id: string;
  last_seen: number;
  name: string;
  nonce: number;
  s_public_key: string;
  signature: string;
}

export interface DORNode {
  dor_service: boolean;
  identity: NodeIdentity;
  last_seen: number;
  p2p_address: string[];
  rest_address: string[];
  retain_job_history: boolean;
  rti_service: boolean;
}

export enum DataFormat {
  JSON = 'json',
  TIFF = 'tiff',
  ARCHIVE_TAR_GZ = 'archive(tar.gz)',
  HDF5 = 'hdf5',
  CSV = 'csv',
  GEOJSON = 'geojson',
}

export enum DataType {
  LczMap = 'DUCT.LCZMap',
  LandUse = 'DUCT.LandUse',
  AHProfile = 'DUCT.AHProfile',
  BuildingDemand = 'BEMCEA.BuildingDemand',
}

export interface UploadFile {
  data_type: DataType;
  data_format: DataFormat;
  restricted_access: boolean;
  content_encrypted: boolean;
  license_by: boolean;
  license_sa: boolean;
  license_nc: boolean;
  license_nd: boolean;
  preferred_dor_iid?: string;
  tags?: UploadTag[];
}

export interface UploadTag {
  key: string;
  value: string;
}

export interface DORObject {
  access: string[];
  access_restricted: boolean;
  c_hash: string;
  created: CreationData;
  custodian: DORNode;
  data_format: DataFormat;
  data_type: DataType;
  obj_id: string;
  owner_iid: string;
  tags: { [key: string]: string };
}

export interface CreationData {
  creators_iid: string[];
  timestamp: number;
}

export interface FileReference {
  name: string;
  type: 'value' | 'reference';
  obj_id?: string;
  value?: object;
}

export const UploadValidationSchema = object().shape({
  tags: array()
    .of(
      object().shape({
        key: string(),
        value: string(),
      })
    )
    .optional(),
  data_type: string().required('Data type is a required field'),
  data_format: string().required('Data format is a required field').min(1),
  restricted_access: boolean().required(),
  content_encrypted: boolean().required(),
  license_by: boolean().required(),
  license_sa: boolean().required(),
  license_nc: boolean().required(),
  license_nd: boolean().required(),
  preferred_dor_iid: string().optional(),
});
