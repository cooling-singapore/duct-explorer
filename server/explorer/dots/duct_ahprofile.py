import json
import os
from typing import Dict, List, Optional, Tuple

from saas.core.helpers import get_timestamp_now
from saas.core.logging import Logging

from duct.analyses.microscale_urban_climate import coord_4326_to_32648, coord_32648_to_4326
from duct.exceptions import DUCTRuntimeError
from duct.renderer.ah_profile_renderer import AHProfileRenderer
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, ImportTarget, DOTVerificationMessage, \
    DOTVerificationResult
from explorer.geodb import GeometryType
from explorer.schemas import ExplorerRuntimeError

logger = Logging.get('duct.dots.ahprofile')


class AnthropogenicHeatProfile(ImportableDataObjectType):
    DATA_TYPE = 'duct.ah-profile'

    VALID_UNITS = {'height': ['m']}
    VALID_UNITS.update({f"AH_{h}": ['W', 'KW', 'MW', 'GW', 'TW'] for h in range(24)})

    @classmethod
    def read_as_geojson(cls, path: str, messages: List[DOTVerificationMessage] = None) -> Optional[List[dict]]:
        try:
            with open(path, 'r') as f:
                content = json.load(f)

                # required properties
                required = ['height', 'AH_type']
                required.extend([f"AH_{h}" for h in range(24)])

                # check each feature
                next_feature_id = 0
                for feature in content['features']:
                    properties = feature['properties'] if 'properties' in feature else {}

                    # verify properties
                    missing = list(required)
                    for key, value in properties.items():
                        if ':' in key:
                            temp = key.split(':')
                            key = temp[0]
                            unit = temp[1]

                            # verify unit
                            if key in cls.VALID_UNITS and unit not in cls.VALID_UNITS[key]:
                                if messages is not None:
                                    messages.append(DOTVerificationMessage(
                                        severity='error', message=f"Units in GeoJSON feature not valid: {key}={value}"
                                    ))
                                return None

                            # verify value (should be float)
                            try:
                                value = float(value)
                            except ValueError:
                                if messages is not None:
                                    messages.append(DOTVerificationMessage(
                                        severity='error', message=f"Invalid value: {key}:{unit}={value}"
                                    ))
                                return None

                        # if the key was missing, remove it as we found it
                        if key in missing:
                            missing.remove(key)

                    # any missing properties?
                    if len(missing) > 0:
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"Missing properties in GeoJSON feature: {', '.join(missing)}"
                            ))
                        return None

                    # verify AH type
                    if properties['AH_type'] not in ['SH', 'LH']:
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"Invalid AH type in GeoJSON feature: {properties['AH_type']}"
                            ))
                        return None

                    # remove properties that are not required
                    feature['properties'] = {
                        key: value for key, value in properties.items()
                        if any(key.startswith(prefix) for prefix in required)
                    }

                    # set the id
                    feature['properties']['id'] = str(next_feature_id)
                    feature['id'] = str(next_feature_id)
                    next_feature_id += 1

                return content

        except Exception:
            return None  # at this point we assume it's not a GeoJSON

    @classmethod
    def read_as_csv(cls, path: str, messages: List[DOTVerificationMessage] = None) -> Optional[dict]:
        try:
            next_feature_id = 0
            with open(path, 'r') as f:
                # read the header
                header = f.readline()
                header = header.split(',')
                header = [field.strip() for field in header]

                # does it start with a {? then it's probably a GeoJSON
                if header[0].startswith('{'):
                    return None

                # verify header part 1
                for i, ref in enumerate(['lon', 'lat', 'height:', 'AH_type']):
                    if not header[i].startswith(ref):
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"CSV header not valid: {','.join(header)}"
                            ))
                        return None

                # verify header part 2
                for h in range(24):
                    if not header[h+4].startswith(f"AH_{h}:"):
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"CSV header not valid: {','.join(header)}"
                            ))
                        return None

                # verify header units
                for field in header:
                    if ':' in field:
                        temp = field.split(':')
                        key = temp[0]
                        unit = temp[1]
                        if key in cls.VALID_UNITS and unit not in cls.VALID_UNITS[key]:
                            if messages is not None:
                                messages.append(DOTVerificationMessage(
                                    severity='error', message=f"Units in CSV header not valid: {','.join(header)}"
                                ))
                            return None

                features = []
                while line := f.readline():
                    line = line.strip().split(',')
                    if len(line) == 1 and line[0] == '':
                        continue

                    elif len(line) != 28:
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"Invalid row: {line}"
                            ))
                        return None

                    # extract lon, lat
                    try:
                        lon = float(line[0])
                        lat = float(line[1])
                    except ValueError:
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"Invalid lon/lat value: {line[0]}, {line[1]}"
                            ))
                        return None

                    # extract height
                    properties = {}
                    try:
                        height = float(line[2])
                        properties[header[2]] = height
                    except ValueError:
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"Invalid height value: {line[2]}"
                            ))
                        return None

                    # verify AH type
                    if line[3] not in ['SH', 'LH']:
                        if messages is not None:
                            messages.append(DOTVerificationMessage(
                                severity='error', message=f"Invalid AH type: {line[3]}"
                            ))
                        return None
                    else:
                        properties[header[3]] = line[3]

                    # verify AH value
                    for h in range(24):
                        try:
                            properties[header[4+h]] = float(line[4+h])
                        except ValueError:
                            if messages is not None:
                                messages.append(DOTVerificationMessage(
                                    severity='error', message=f"Invalid AH value: {line[2]}"
                                ))
                            return None

                    # create GeoJSON feature
                    properties['id'] = str(next_feature_id)
                    features.append({
                        'type': 'Feature',
                        'id': str(next_feature_id),
                        'properties': properties,
                        'geometry': {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        }
                    })

                    next_feature_id += 1

                return {
                    'type': 'FeatureCollection',
                    'features': features
                }

        except Exception:
            return None  # at this point we assume it's not a GeoJSON

    def target(self) -> ImportTarget:
        return ImportTarget.library

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Anthropogenic Heat Profile'

    def supported_formats(self) -> List[str]:
        return ['geojson', 'csv']

    def description(self) -> str:
        return "Anthropogenic Heat (AH) Profile data is a set of polygons, each representing an area with AH " \
               "emissions at a certain height. For each area, a diurnal emission profile is defined, indicating the " \
               "intensity of AH emissions for each hour of the day. In addition, it is possible to distinguish " \
               "between sensible and latent heat. The acceptable formats and attributes are listed below. <br><br> " \
               "<b>Required data attributes:</b>" \
               "<ul><li>Emission areas (polygons geo-referenced with WGS84 coordinate system) </li>" \
               "<li>Height at which heat is emitted (in meters)</li> " \
               "<li>AH emission (in Watts per square meter) for each hour of the day</li></ul> " \
               "<b>Accepted file formats:</b>" \
               "<ul><li>geojson</li></ul>"

    def preview_image_url(self) -> str:
        return 'dot_ah-profile.png'

    def upload_postprocess(self, project, temp_obj_path: str) -> List[Tuple[str, str, UploadPostprocessResult]]:
        from explorer.project import Project
        project: Project = project

        # load the geometries into the geo db
        obj_id = f"{self.name()}_{get_timestamp_now()}"
        obj_path = os.path.join(project.info.temp_path, obj_id)

        # it went already through verify, so we really should have the content here
        content = self.read_as_geojson(temp_obj_path)
        if content is None:
            content = self.read_as_csv(temp_obj_path)

        # we are not splitting, so just copy the file
        with open(obj_path, 'w') as f:
            json.dump(content, f, indent=2)

        # update AH features
        AnthropogenicHeatProfile.update_ah_features(obj_path)

        result = [(obj_id, obj_path, UploadPostprocessResult(title='Update AH Profile Attributes',
                                                             description='', mode='fix-attr-and-skip',
                                                             extra={}))]
        return result

    def update_preimport(self, project, obj_path: str, args: dict,
                         geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        # does the geo_type make sense?
        if geo_type is not None:
            raise ExplorerRuntimeError(f'[{self.name()}] Unexpected geo_type during pre-import update: {geo_type}')

        ## the following reads the features that are in the uploaded-but-not-yet-imported geojson file on the server
        ## and then adds (or replaces) features that came in through the update request -> add if feature with given
        ## id doesn't already exist, or replace if there was a feature with that id.


        # read the features from the file and map them via id
        features: Dict[str, dict] = {}
        with open(obj_path, 'r') as f:
            content = json.load(f)
            for feature in content['features']:
                features[feature['properties']['id']] = feature

        # update the features with whatever we can find in the args
        if 'features' in args:
            for feature in args['features']:
                # update the feature
                features[feature['properties']['id']] = feature

        # write the updated features
        with open(obj_path, 'w') as f:
            f.write(json.dumps({
                'type': 'FeatureCollection',
                'features': list(features.values())
            }))

        # update AH features
        AnthropogenicHeatProfile.update_ah_features(obj_path)

        return UploadPostprocessResult(title='Update AH Profile Attributes', description='', mode='skip', extra={})

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        # try to read as CSV first. if that doesn't work try to read as GeoJSON:
        messages = []
        content, data_format = self.read_as_geojson(content_path, messages), 'geojson'
        if content is None:
            content, data_format = self.read_as_csv(content_path, messages), 'csv'

        # if we don't have any content here, then we couldn't read the data
        if content is None:
            data_format = 'unknown'
            messages.append(DOTVerificationMessage(
                severity='error', message=f"Data cannot be read as CSV or GeoJSON."
            ))

        # do we have any errors?
        is_verified = True
        for message in messages:
            if message.severity == 'error':
                is_verified = False
                break

        return DOTVerificationResult(messages=messages, is_verified=is_verified, data_format=data_format)

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        with open(content_path, 'r') as f:
            content = json.load(f)

        for feature in content['features']:
            # is it a point geometry?
            if feature['geometry']['type'] == 'Point':
                # determine bounding box around point with the size of a 100x100 meters
                p = coord_4326_to_32648(feature['geometry']['coordinates'])
                west = p[0] - 50
                east = p[0] + 50
                south = p[1] - 50
                north = p[1] + 50

                # convert north/west and south/east into epsg:4326
                p_nw = coord_32648_to_4326((west, north))
                p_se = coord_32648_to_4326((east, south))

                west = p_nw[0]
                east = p_se[0]
                south = p_se[1]
                north = p_nw[1]

                feature['geometry'] = {
                    "type": "Polygon",
                    "coordinates": [[(west, north), (east, north), (east, south), (west, south), (west, north)]]
                }

        # determine max total AH and unit
        total_ah_max = 0.0
        total_ah_unit = None
        for feature in content['features']:
            total_ah_max = max(total_ah_max, feature['properties']['total_AH'])
            total_ah_unit = feature['properties']['total_AH_unit']

        ah_profile_renderer = AHProfileRenderer()

        return {
            "type": "geojson",
            "title": "Anthropogenic Heat Profile",
            "geojson": content,
            "renderer": ah_profile_renderer.renderer("Anthropogenic Heat Profile",
                                                     "total_AH",
                                                     f"Anthropogenic (Sensible+Latent) Heat Emissions (in {total_ah_unit})",
                                                     True)
        }

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    @classmethod
    def update_ah_features(cls, content_path: str) -> None:
        # load the contents
        with open(content_path, 'r') as f:
            content = json.load(f)

        # determine the total AH for each feature with consistent unit across all features
        multipliers = {'W': 1, 'KW': 1e3, 'MW': 1e6, 'GW': 1e9, 'TW': 1e12}
        max_ah = 0.0
        for feature in content['features']:
            properties = feature['properties']
            total_ah = 0.0

            for k, v in properties.items():
                if k != 'AH_type' and k.startswith('AH_'):
                    temp = k[3:].split(':')
                    unit = temp[1]

                    # convert value to [W] and add to total
                    value = float(v) * multipliers[unit]
                    total_ah += value

            # set the total AH as property
            properties['total_AH'] = total_ah

            # update max
            max_ah = max(max_ah, total_ah)

        # determine unit and multiplier based on max AH
        if max_ah / 1e12 > 0:
            unit = 'TW'
            m = 1e12
        elif max_ah / 1e9 > 0:
            unit = 'GW'
            m = 1e9
        elif max_ah / 1e6 > 0:
            unit = 'MW'
            m = 1e6
        elif max_ah / 1e3 > 0:
            unit = 'MW'
            m = 1e3
        else:
            unit = 'W'
            m = 1

        # update total AH value accordingly
        for feature in content['features']:
            properties = feature['properties']
            properties['total_AH'] = properties['total_AH'] / m
            properties['total_AH_unit'] = unit

        # write the contents
        with open(content_path, 'w') as f:
            json.dump(content, f)
