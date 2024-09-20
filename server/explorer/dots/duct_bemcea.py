import json
import shutil
from typing import Dict, List, Tuple
from itertools import cycle, combinations

import numpy as np
import pandas as pd
from saas.core.logging import Logging

from duct.exceptions import DUCTRuntimeError
from duct.renderer.district_cooling_network_renderer import DistrictCoolingNetworkRenderer
from explorer.dots.dot import DataObjectType
from explorer.renderer.buildings_renderer import BuildingConnectRenderer

logger = Logging.get('duct.dots.bemcea')


def aggregate_ah_data(data_path: str) -> Dict[str, Dict[str, List[float]]]:
    with open(data_path, 'r') as f:
        # read header
        f.readline().strip().split(',')

        # read the emission data
        structured: Dict[str, Dict[str, Dict[int, List[float]]]] = {}
        while (line := f.readline()) not in [None, '']:
            line = line.strip().split(',')

            # get the data for this folder name
            folder_name = line[0]
            if folder_name not in structured:
                structured[folder_name] = {}
            data: Dict[str, Dict[int, List[float]]] = structured[folder_name]

            # get the data for this building/network entity
            entity_name = line[2]
            if entity_name not in data:
                data[entity_name] = {h: [] for h in range(24)}
            data: Dict[int, List[float]] = data[entity_name]

            # add 24 data points
            for h in range(24):
                value = float(line[3+h])
                data[h].append(value)

        # build statistics
        aggregated: Dict[str, Dict[str, List[float]]] = {}
        for folder_name, data0 in structured.items():
            aggregated[folder_name] = {}
            for entity_name, data1 in data0.items():
                values = []
                for h in range(24):
                    mean = np.mean(data1[h])
                    values.append(mean)

                aggregated[folder_name][entity_name] = values

        return aggregated


def hash_feature(feature: dict) -> int:
    """
    Get feature hash based on their geometry coordinates
    (rounded to 5 decimal places to account for floating errors)
    """
    coordinates = feature["geometry"]["coordinates"][0]

    return hash(tuple(
        hash(
            (round(coords[0], 5), round(coords[1], 5))
        ) for coords in coordinates
    ))


def get_common_features_indexes(geojson0: dict, geojson1: dict) -> List[Tuple[int, int]]:
    """
    Finds the indexes of common features in each geojson
    """
    hashes_0 = {hash_feature(feature): i for i, feature in enumerate(geojson0["features"])}
    hashes_1 = {hash_feature(feature): i for i, feature in enumerate(geojson1["features"])}

    common_hashes = hashes_0.keys() & hashes_1.keys()

    return sorted([(hashes_0[h], hashes_1[h]) for h in common_hashes], key=lambda x: x[0])


def compute_delta_data(geojson_0: dict, geojson_1: dict, building_footprints_0: dict, building_footprints_1: dict, field_name: str) -> list:
    common_features_indexes = get_common_features_indexes(building_footprints_0, building_footprints_1)

    if not len(common_features_indexes):
        raise DUCTRuntimeError("Could not find any common buildings in both analyses")

    # extract delta data from geojsons
    def get_delta_data(features_0: Dict, features_1: Dict) -> float:
        a = features_0['properties'][field_name]
        b = features_1['properties'][field_name]
        return a - b

    # map building data to building_footprints
    def add_building_data(feature: Dict, data: float):
        feature['properties'][field_name] = round(data)
        return feature

    # compute delta for common buildings
    delta_features = []
    for indexes in common_features_indexes:
        feature_0 = geojson_0['features'][indexes[0]]
        feature_1 = geojson_1['features'][indexes[1]]
        delta = get_delta_data(feature_0, feature_1)
        delta_feature = add_building_data(feature_0, delta)
        delta_features.append(delta_feature)

    return delta_features


def compute_delta_export_data(geojson_0: dict, geojson_1: dict, building_footprints_0: dict, building_footprints_1: dict,
                          field_name: str) -> dict:
    common_features_indexes = get_common_features_indexes(building_footprints_0, building_footprints_1)

    if not len(common_features_indexes):
        raise DUCTRuntimeError("Could not find any common buildings in both analyses")

    # calculate delta for each common building and update properties
    delta_features = []
    for indexes in common_features_indexes:
        feature_0 = geojson_0['features'][indexes[0]]
        feature_1 = geojson_1['features'][indexes[1]]

        delta = round(feature_0['properties'][field_name] - feature_1['properties'][field_name], 2)

        delta_feature = feature_0.copy()
        delta_feature['properties'][field_name] = delta
        delta_features.append(delta_feature)

    delta_geojson = {
        'type': 'FeatureCollection',
        'features': delta_features
    }

    return delta_geojson


def get_geojson_property_range(geojson: dict, property_name: str) -> Tuple[int, int]:
    return (
        max((f["properties"][property_name] for f in geojson["features"] if f["properties"][property_name] is not None),
            default=0),
        min((f["properties"][property_name] for f in geojson["features"] if f["properties"][property_name] is not None),
            default=0)
    )


def generate_building_map(title: str, field: str, units: str, geojson: dict) -> dict:
    """
    Generate map visualisation spec based on arcgis renderer

    renderer docs: https://developers.arcgis.com/javascript/latest/sample-code/visualization-vv-extrusion/
    """
    _range = get_geojson_property_range(geojson, field)
    return {
        "type": "geojson",
        "title": title,
        "renderer": {
            "type": "simple",
            "symbol": {
                "type": "polygon-3d",
                "symbolLayers": [
                    {
                        "type": "extrude",
                        "edges": {
                            "type": "solid",
                            "color": [
                                1,
                                1,
                                1
                            ],
                            "size": 0.5
                        }
                    }
                ]
            },
            "label": "Buildings",
            "visualVariables": [
                {
                    "type": "size",
                    "field": "height",
                    "valueUnit": "meters",
                    "legendOptions": {
                        "showLegend": False
                    }
                },
                {
                    "type": "color",
                    "field": field,
                    "legendOptions": {
                        "title": f"{title} ({units})"
                    },
                    "stops": [
                        {
                            "value": round(_range[0]),
                            "color": "#350242",
                            "label": round(_range[0])
                        },
                        {
                            "value": round(_range[1]),
                            "color": "#FFFCD4",
                            "label": round(_range[1])
                        }
                    ]
                }
            ]
        },
        "popupTemplate": {
            "title": "Building Info",
            "expressionInfos": [{
                "name": "building-type-mapping",
                "title": "Building Type",
                "expression": "var type = $feature.building_type; "
                              "return Decode(type, 'commercial:1', 'Office', 'residential:1', 'Residential', "
                              "'commercial:2', 'Hotel', 'commercial:3', 'Retail', 'Other');"
            }],
            "content": [
                {
                    "type": "fields",
                    "fieldInfos": [
                        {
                            "fieldName": "id",
                            "label": "Building Id"
                        },
                        {
                            "fieldName": "actual_name",
                            "label": "Building Name"
                        },
                        {
                            "fieldName": "expression/building-type-mapping"
                        },
                        {
                            "fieldName": "height",
                            "label": "Height"
                        },
                        {
                            "fieldName": "area",
                            "label": "Area",
                            "format": {
                                "digitSeparator": True,
                                "places": 2
                            }
                        },
                        {
                            "fieldName": field,
                            "label": title
                        }
                    ]
                }
            ]
        },
        "labelingInfo": [
            {
                "symbol": {
                    "type": "label-3d",
                    "symbolLayers": [
                        {
                            "type": "text",
                            "material": {
                                "color": "black",
                            },
                            "halo": {
                                "color": "white",
                                "size": 3,
                            },
                            "size": 10,
                        },
                    ],
                },
                "labelExpressionInfo": {
                    "expression": 'DefaultValue($feature.actual_name, "Unknown")'
                },
                "minScale": 2500
            }
        ],
        "geojson": geojson
    }


def generate_building_bar_chart(title: str, subtitle: str, field: str, geojson: dict, x_ticks: bool = True) -> Dict:
    # determine labels and data lists
    labels = []
    data = []
    for feature in geojson["features"]:
        properties = feature['properties']
        name = str(properties['actual_name'])
        value = properties[field]
        labels.append(name)
        data.append(value)

    return {
        'lib': 'chart.js',
        'type': 'bar',
        'data': {
            'labels': labels,
            'datasets': [
                {
                    'label': subtitle,
                    'data': data,
                    'backgroundColor': '#2C5B74'
                }
            ]
        },
        'options': {
            'responsive': True,
            'plugins': {
                'legend': {
                    'position': 'bottom'
                },
                'title': {
                    'display': True,
                    'text': title
                }
            },
            'scales': {
                'x': {
                    'display': x_ticks
                }
            }
        }
    }


class BuildingAnnualEnergy(DataObjectType):
    DATA_TYPE = 'duct.BuildingAnnualEnergy'

    def _merge_to_building_properties(self, annual_energy_data_path: str, building_footprints: dict) -> dict:
        # read the annual energy data
        with open(annual_energy_data_path, 'r') as f:
            annual_energy_data = json.load(f)

        # add the annual energy data to the building feature properties
        for feature in building_footprints['features']:
            properties = feature['properties']

            # get data for this building
            building_id = str(feature['properties']['id'])
            if building_id in annual_energy_data:
                properties['energy_consumption'] = annual_energy_data[building_id]['GRID_MWhyr']
                properties['GFA'] = annual_energy_data[building_id]['GFA_m2']
                properties['EUI'] = annual_energy_data[building_id]['EUI_kWhyrm2']
                properties['EEI'] = annual_energy_data[building_id]['EEI_kWhyrm2']
                properties['operating_hours'] = annual_energy_data[building_id]['OH_h']
            else:
                properties['energy_consumption'] = 0
                properties['GFA'] = 0
                properties['EUI'] = 0
                properties['EEI'] = 0
                properties['operating_hours'] = 0

        return building_footprints

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Building Annual Energy'

    def supported_formats(self) -> List[str]:
        return ['geojson']

    def extract_feature(self, content_path: str, parameters: dict) -> List[Dict]:
        # read the annual energy data and merge with building properties
        geojson = self._merge_to_building_properties(content_path, parameters.get('building_footprints'))

        titles = {
            'energy_consumption': 'Annual Energy Consumption',
            'energy_use_intensity': 'Energy Use Intensity (EUI)',
            'energy_efficiency_index': 'Energy Efficiency Index (EEI)'
        }

        fields = {
            'energy_consumption': 'energy_consumption',
            'energy_use_intensity': 'EUI',
            'energy_efficiency_index': 'EEI'
        }

        units = {
            'energy_consumption': 'MWh',
            'energy_use_intensity': 'kWh/m^2',
            'energy_efficiency_index': 'kWh/m^2'
        }

        variable = parameters['variable']
        map_spec = generate_building_map(titles[variable], fields[variable], units[variable], geojson)
        chart_spec = generate_building_bar_chart(titles[variable],
                                                 f"{titles[variable]} ({units[variable]}) per building",
                                                 fields[variable], geojson, False)

        return [map_spec, chart_spec]

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> List[Dict]:
        variable = parameters['A']['variable']

        building_footprints_0: dict = parameters['A'].get('building_footprints')
        building_footprints_1: dict = parameters['B'].get('building_footprints')

        geojson_0 = self._merge_to_building_properties(content_path0, building_footprints_0)
        geojson_1 = self._merge_to_building_properties(content_path1, building_footprints_1)

        fields = {
            'energy_consumption': 'energy_consumption',
            'energy_use_intensity': 'EUI',
            'energy_efficiency_index': 'EEI'
        }

        units = {
            'energy_consumption': 'MWh',
            'energy_use_intensity': 'kWh/m^2',
            'energy_efficiency_index': 'kWh/m^2'
        }

        field_name = fields[variable]

        # compute delta for common buildings
        delta_features = compute_delta_data(geojson_0, geojson_1, building_footprints_0, building_footprints_1, field_name)

        delta_geojson = {
            'type': 'FeatureCollection',
            'features': delta_features
        }

        title = variable.replace('_', ' ').title()

        return generate_building_map(title, field_name, units[variable], delta_geojson)

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'geojson':
            # read the annual energy data and merge with building properties
            geojson = self._merge_to_building_properties(content_path, parameters.get('building_footprints'))

            # write the combined data to the export destination
            with open(export_path, 'w') as f:
                json.dump(geojson, f, indent=2)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        if export_format == 'geojson':
            building_footprints_0: dict = parameters['A'].get('building_footprints')
            building_footprints_1: dict = parameters['B'].get('building_footprints')

            geojson_0 = self._merge_to_building_properties(content_path0, parameters['A'].get('building_footprints'))
            geojson_1 = self._merge_to_building_properties(content_path1, parameters['B'].get('building_footprints'))

            variable = parameters['A']['variable']

            fields = {
                'energy_consumption': 'energy_consumption',
                'energy_use_intensity': 'EUI',
                'energy_efficiency_index': 'EEI'
            }
            field_name = fields[variable]

            delta_geojson = compute_delta_export_data(geojson_0, geojson_1, building_footprints_0, building_footprints_1, field_name)

            with open(export_path, 'w') as f:
                json.dump(delta_geojson, f, indent=2)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")


class BuildingAnnualGeneration(DataObjectType):
    DATA_TYPE = 'duct.BuildingAnnualGeneration'

    def _merge_to_building_properties(self, data_path: str, building_footprints: dict) -> dict:
        # read the data
        with open(data_path, 'r') as f:
            data = json.load(f)

        columns = ['E_gen_roof_kWhyr', 'E_gen_walls_kWhyr', 'E_gen_total_kWhyr', 'PV_roof_area_m2',
                   'PV_walls_area_m2', 'PV_total_area_m2', 'total_radiation_kWhyr', 'GFA_m2', 'EGI_kWhyrm2',
                   'EUI_kWhyrm2', 'EGI_EUI_ratio']

        # add the data to the building feature properties
        for feature in building_footprints['features']:
            properties = feature['properties']

            # get data for this building
            building_id = str(feature['properties']['id'])
            if building_id in data:
                for c in columns:
                    properties[c] = data[building_id][c]
            else:
                for c in columns:
                    properties[c] = 0

        return building_footprints

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Building Annual Generation'

    def supported_formats(self) -> List[str]:
        return ['geojson']

    def extract_feature(self, content_path: str, parameters: dict) -> List[Dict]:
        # read the data and merge with building properties
        geojson = self._merge_to_building_properties(content_path, parameters.get('building_footprints'))

        titles = {
            'energy_generation': 'Annual Energy Generation',
            'energy_generation_intensity': 'Energy Generation Intensity (EGI)',
            'generation_consumption_ratio': 'Generation Consumption Ratio'
        }

        fields = {
            'energy_generation': 'E_gen_total_kWhyr',
            'energy_generation_intensity': 'EGI_kWhyrm2',
            'generation_consumption_ratio': 'EGI_EUI_ratio'
        }

        units = {
            'energy_generation': 'kWh',
            'energy_generation_intensity': 'kWh/m^2',
            'generation_consumption_ratio': '-'
        }

        variable = parameters['variable']
        map_spec = generate_building_map(titles[variable], fields[variable], units[variable], geojson)
        chart_spec = generate_building_bar_chart(titles[variable],
                                                 f"{titles[variable]} ({units[variable]}) per building",
                                                 fields[variable], geojson, False)

        return [map_spec, chart_spec]

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> List[Dict]:
        variable = parameters['A']['variable']

        building_footprints_0: dict = parameters['A'].get('building_footprints')
        building_footprints_1: dict = parameters['B'].get('building_footprints')

        geojson_0 = self._merge_to_building_properties(content_path0, building_footprints_0)
        geojson_1 = self._merge_to_building_properties(content_path1, building_footprints_1)

        fields = {
            'energy_generation': 'E_gen_total_kWhyr',
            'energy_generation_intensity': 'EGI_kWhyrm2',
            'generation_consumption_ratio': 'EGI_EUI_ratio'
        }

        units = {
            'energy_generation': 'kWh',
            'energy_generation_intensity': 'kWh/m^2',
            'generation_consumption_ratio': '-'
        }

        field_name = fields[variable]

        delta_features = compute_delta_data(geojson_0, geojson_1, building_footprints_0, building_footprints_1, field_name)

        delta_geojson = {
            'type': 'FeatureCollection',
            'features': delta_features
        }

        title = variable.replace('_', ' ').title()

        return generate_building_map(title, field_name, units[variable], delta_geojson)

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'geojson':
            # read the data and merge with building properties
            geojson = self._merge_to_building_properties(content_path, parameters.get('building_footprints'))

            # write the combined data to the export destination
            with open(export_path, 'w') as f:
                json.dump(geojson, f, indent=2)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        if export_format == 'geojson':
            building_footprints_0: dict = parameters['A'].get('building_footprints')
            building_footprints_1: dict = parameters['B'].get('building_footprints')

            geojson_0 = self._merge_to_building_properties(content_path0, parameters['A'].get('building_footprints'))
            geojson_1 = self._merge_to_building_properties(content_path1, parameters['B'].get('building_footprints'))

            variable = parameters['A']['variable']

            fields = {
                'energy_generation': 'E_gen_total_kWhyr',
                'energy_generation_intensity': 'EGI_kWhyrm2',
                'generation_consumption_ratio': 'EGI_EUI_ratio'
            }

            field_name = fields[variable]

            delta_geojson = delta_geojson = compute_delta_export_data(geojson_0, geojson_1, building_footprints_0, building_footprints_1, field_name)

            with open(export_path, 'w') as f:
                json.dump(delta_geojson, f, indent=2)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")


class BuildingAHEmissions(DataObjectType):
    DATA_TYPE = 'duct.building-ah-emissions'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Building Anthropogenic Heat Emissions'

    def supported_formats(self) -> List[str]:
        return ['geojson']

    def extract_feature(self, content_path: str, parameters: dict) -> List[Dict]:
        # aggregate the data and extract the variable of interest
        data: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(content_path)
        data: Dict[str, List[float]] = data[parameters['variable']]

        def add_emission_data(feature: dict):
            bld_id = str(feature['properties']['id'])
            ah_emissions = data.get(bld_id, [-1 for _ in range(24)])
            for h in range(24):
                feature['properties'][f'AH_{h}'] = ah_emissions[h]
            return feature

        # build geojson from building footprints and emission data
        building_footprints: dict = parameters.get('building_footprints')
        geojson = {
            'type': 'FeatureCollection',
            'features': [add_emission_data(feature) for feature in building_footprints['features']]
        }

        hour = parameters['hour']
        map_spec = generate_building_map('Building AH Emissions', f'AH_{hour}', 'kW', geojson)
        chart_spec = generate_building_bar_chart('Building AH Emissions',
                                                 f'Building AH Emissions (kW) per building at {hour} hours',
                                                 f'AH_{hour}', geojson, False)

        return [map_spec, chart_spec]

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        # aggregate the data and extract the variable of interest
        data_0: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(content_path0)
        data_0: Dict[str, List[float]] = data_0[parameters['A']['variable']]

        data_1: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(content_path1)
        data_1: Dict[str, List[float]] = data_1[parameters['B']['variable']]

        def add_emission_data(feature: dict, data: dict):
            bld_id = str(feature['properties']['id'])
            ah_emissions = data.get(bld_id, [-1 for _ in range(24)])
            for h in range(24):
                feature['properties'][f'AH_{h}'] = ah_emissions[h]
            return feature

        # build geojson from building footprints and emission data
        building_footprints_0: dict = parameters['A'].get('building_footprints')
        building_footprints_1: dict = parameters['B'].get('building_footprints')

        geojson_0 = {
            'type': 'FeatureCollection',
            'features': [add_emission_data(feature, data_0) for feature in building_footprints_0['features']]
        }

        geojson_1 = {
            'type': 'FeatureCollection',
            'features': [add_emission_data(feature, data_1) for feature in building_footprints_1['features']]
        }

        hour = parameters['A']['hour']
        field_name = 'AH_' + str(hour)

        # compute delta for common buildings
        delta_features = compute_delta_data(geojson_0, geojson_1, building_footprints_0, building_footprints_1, field_name)

        delta_geojson = {
            'type': 'FeatureCollection',
            'features': delta_features
        }

        return generate_building_map('Building AH Emissions', f'AH_{hour}', 'kW', delta_geojson)

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'geojson':
            # aggregate the data and extract the variable of interest
            data: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(content_path)
            data: Dict[str, List[float]] = data[parameters['variable']]

            def add_emission_data(feature: dict):
                bld_id = feature['properties']['id']
                ah_emissions = data.get(bld_id, [-1 for _ in range(24)])
                feature['properties']['ah_emissions'] = ah_emissions

            # build geojson from building footprints and emission data
            building_footprints: dict = parameters.get('building_footprints')
            geojson = {
                'type': 'FeatureCollection',
                'features': [add_emission_data(feature) for feature in building_footprints['features']]
            }

            # write the file
            with open(export_path, 'w') as f:
                json.dump(geojson, f, indent=2)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        if export_format == 'geojson':
            data_0: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(content_path0)
            data_0: Dict[str, List[float]] = data_0[parameters['A']['variable']]

            data_1: Dict[str, Dict[str, List[float]]] = aggregate_ah_data(content_path1)
            data_1: Dict[str, List[float]] = data_1[parameters['B']['variable']]

            def add_emission_data(feature: dict, data: dict):
                bld_id = str(feature['properties']['id'])
                ah_emissions = data.get(bld_id, [-1 for _ in range(24)])
                for h in range(24):
                    feature['properties'][f'AH_{h}'] = ah_emissions[h]
                return feature

            # build geojson from building footprints and emission data
            building_footprints_0: dict = parameters['A'].get('building_footprints')
            building_footprints_1: dict = parameters['B'].get('building_footprints')

            geojson_0 = {
                'type': 'FeatureCollection',
                'features': [add_emission_data(feature, data_0) for feature in building_footprints_0['features']]
            }

            geojson_1 = {
                'type': 'FeatureCollection',
                'features': [add_emission_data(feature, data_1) for feature in building_footprints_1['features']]
            }

            hour = parameters['A']['hour']
            field_name = f"AH_{hour}"

            delta_geojson = delta_geojson = compute_delta_export_data(geojson_0, geojson_1, building_footprints_0, building_footprints_1, field_name)

            with open(export_path, 'w') as f:
                json.dump(delta_geojson, f, indent=2)

        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")


def create_highlighted_scatter_chart(system_names: List[str],
                                     x_title: List[str], y_title: List[str],
                                     x_data: List, y_data: List,
                                     highlighted_index: int,
                                     color: str = 'rgb(75, 192, 192)',
                                     highlighted_color: str = 'rgb(255, 0, 0)') -> dict:

    colors = [color if i != highlighted_index else highlighted_color for i, _ in enumerate(x_data)]
    radius = [3 if i != highlighted_index else 5 for i, _ in enumerate(x_data)]

    return {
        'lib': 'chart.js',
        'type': 'scatter',
        'data': {
            'labels': system_names,
            'datasets': [
                {
                    'data': [{
                        "x": x,
                        "y": y
                    } for x, y in zip(x_data, y_data)],
                    'pointBackgroundColor': colors,
                    'pointRadius': radius,
                    'showLine': True,
                    'tension': 0.2
                }
            ]
        },
        'options': {
            'responsive': True,
            'scales': {
                'x': {
                    'title': {
                        'text': x_title,
                        'display': True
                    }
                },
                'y': {
                    'title': {
                        'text': y_title,
                        'display': True
                    }
                }
            },
            'plugins': {
                'title': {
                    'display': True,
                    'text': f'{y_title[0]} vs {x_title[0]}'
                },
                'legend': {
                    'display': False
                }
            }
        }
    }


def create_system_summary_charts(all_dcs: dict, selected_system_name: str) -> List[dict]:
    summary_keys = ["Heat_Emissions_kWh", "System_Energy_Demand_kWh", "GHG_Emissions_kgCO2", "Cost_USD"]

    """
    Creates scatter plot charts that help compare the selected system objectives with the other possible systems
    """
    # for each system, determine the summary totals
    system_totals = {}
    for system_name, clusters in all_dcs.items():
        system_totals[system_name] = {k: 0 for k in summary_keys}
        for cluster_name, data in clusters.items():
            summary = data['summary']
            for k in summary_keys:
                system_totals[system_name][k] += summary[k]

    # Create bar charts for each objective from system totals
    bar_charts = []
    objective_functions = [
        {'title': ['System Cost', '(USD in Millions)'], 'data_column_name': 'Cost_USD'},
        {'title': ['System Energy Demand', '(GWh)'], 'data_column_name': 'System_Energy_Demand_kWh'},
        {'title': ['System Heat Emissions', '(GWh)'], 'data_column_name': 'Heat_Emissions_kWh'}
    ]

    # Generate combinations of objective functions for pareto front chart
    for obj_x, obj_y in combinations(objective_functions, 2):
        _data = [(k,
                  round(int(v[obj_x["data_column_name"]])/(1000 * 1000), 3),
                  round(int(v[obj_y["data_column_name"]])/(1000 * 1000), 3)
                  )
                 for k, v in system_totals.items()]

        system_names, data_x, data_y = zip(*sorted(_data, key=lambda a: a[2], reverse=True))
        bar_charts.append(create_highlighted_scatter_chart(
            system_names=system_names,
            x_title=obj_x["title"],
            y_title=obj_y["title"],
            x_data=data_x,
            y_data=data_y,
            highlighted_index=system_names.index(selected_system_name)
        ))

    return bar_charts


def create_network_map(network: dict, system_name: str, cluster_name: str) -> dict:
    # separate points and lines to show network on map
    points = []
    lines = []
    for feature in network['features']:
        geometry_type = feature["geometry"]["type"]
        if geometry_type == "Point":
            points.append(feature)
        elif geometry_type == "LineString":
            lines.append(feature)

    renderer = DistrictCoolingNetworkRenderer()
    network_map = {
        "type": "network",
        "title": f"{renderer.title()} ({system_name}: {cluster_name})",
        "pointData": {
            "type": "geojson",
            "title": renderer.point_title(),
            "geojson": {
                "type": "FeatureCollection",
                "features": points
            },
            "renderer": renderer.point_renderer(),
            "labelingInfo": [
                {
                    "symbol": {
                      "type": "label-3d",
                      "symbolLayers": [
                        {
                          "type": "text",
                          "material": {
                            "color": "black",
                          },
                          "halo": {
                            "color": "white",
                            "size": 3,
                          },
                          "size": 10,
                        },
                      ],
                    },
                    "labelPlacement": "above-center",
                    "labelExpression": "DC Plant",
                    "where": "Type = 'PLANT'"
                }
            ]
        },
        "lineData": {
            "type": "geojson",
            "title": renderer.line_title(),
            "geojson": {
                "type": "FeatureCollection",
                "features": lines
            },
            "renderer": renderer.line_renderer()
        }
    }

    return network_map


def create_connected_building_map(network_map: dict, building_footprints: dict) -> dict:
    # extract building names connected to points
    building_ids = []
    connected_point_list = network_map['pointData']['geojson']['features']
    for connected_point in connected_point_list:
        if 'properties' in connected_point and 'Building' in connected_point['properties'] \
                and connected_point['properties']['Building'] != 'NONE':
            building_ids.append(connected_point['properties']['Building'])

    # add 'connected' flag to building footprints
    if 'features' in building_footprints:
        for building in building_footprints['features']:
            if 'id' in building['properties'] and str(building['properties']['id']) in building_ids:
                building['properties']['connected'] = 'connected'
            else:
                building['properties']['connected'] = 'not_connected'

    return {
        "type": "geojson",
        "title": "Selected buildings",
        "geojson": building_footprints,
        "renderer": BuildingConnectRenderer().get()
    }


def create_pie_charts(structure: List[dict]) -> List[dict]:
    component_structure = pd.DataFrame(structure)

    # Create pie charts based on components
    pie_charts = []
    colors = ["#75e8b9", "#2c5b74", "#3c7b9a", "#4999c3"]
    cat_title_map = {
        "primary": "Cooling Components Capacity (MW)",
        "secondary": "Supply Components Capacity (MW)",
        "tertiary": "Heat Rejection Components Capacity (MW)",
    }

    for cat, group in component_structure.groupby("Category"):
        components = (group["Component"] + " (" + group["Component_type"] + ")").tolist()
        capacity = group["Capacity_kW"].round().tolist()
        _colors = cycle(colors)

        chart = {
            'lib': 'chart.js',
            'type': 'pie',
            'data': {
                'labels': components,
                'datasets': [{
                    'label': cat_title_map[cat],
                    'data': capacity,
                    'backgroundColor': [next(_colors) for _ in capacity]
                }]
            },
            'options': {
                'responsive': True,
                'plugins': {
                    'legend': {
                        'position': 'bottom',
                    },
                    'title': {
                        'display': True,
                        'text': cat_title_map[cat]
                    }

                },
            }
        }

        pie_charts.append(chart)

    return pie_charts


def create_network_flow_chart(structure: List[dict]) -> dict:
    component_structure = pd.DataFrame(structure)

    """
    Create flow chart based on component structure of the system.
    Parent nodes are based on the component categories: primary, secondary, tertiary

    """
    nodes = []
    edges = []

    categories = component_structure["Category"].unique()
    category_labels = {
        "primary": "Cooling Components",
        "secondary": "Supply Components",
        "tertiary": "Heat rejection Components"
    }

    # Add nodes
    for category in categories:
        if category not in category_labels.keys():
            raise ValueError(f"Unknown category: {category}")

        # Parent node
        nodes.append({
            'id': category,
            'data': {
                'label': category_labels[category]
            }
        })

        # Child nodes
        child_components = component_structure[component_structure["Category"] == category]
        for component in child_components.iterrows():
            _, data = component
            nodes.append(
                {
                    'id': data['Component_code'],
                    'data': {
                        'label': f"{data['Component']} ({data['Component_code']})",
                        'description': data['Component_type'],
                        'capacity_kW': data['Capacity_kW']
                    },
                    'parentNode': category
                }
            )

    # Add edges
    sources = {}

    def add_source(source: str) -> None:
        if source not in sources:
            sources[source] = []
        sources[source].append(component_code)

    def add_edges(energy_code: str, sink: str) -> None:
        for source in sources.get(energy_code, []):
            edges.append({
                'id': f"e-{source}-{sink}",
                'source': source,
                'target': sink
            })

    # Go through possible energy sources
    for component in component_structure.iterrows():
        _, data = component
        component_code = data['Component_code']

        # Check main side
        if data['Main_side'] == "output":
            add_source(data['Main_energy_carrier_code'])
        # Check other outputs
        for energy_code in data['Other_outputs'].split(","):
            add_source(energy_code.strip())

    # Go through possible energy sinks
    for component in component_structure.iterrows():
        _, data = component
        component_code = data['Component_code']

        # Check main side
        if data['Main_side'] == "input":
            add_edges(data['Main_energy_carrier_code'], component_code)
        # Check other inputs
        for energy_code in data['Other_inputs'].split(","):
            add_edges(energy_code.strip(), component_code)

    chart = {
        'lib': 'react-flow',
        'type': 'flow_chart',
        'data': {
            'nodes': nodes,
            'edges': edges

        }
    }

    return chart


class SupplySystems(DataObjectType):
    DATA_TYPE = 'duct.supply-systems'

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Supply Systems'

    def supported_formats(self) -> List[str]:
        return ['json']

    def extract_feature(self, content_path: str, parameters: dict) -> List[Dict]:
        # read the JSON content
        with open(content_path, 'r') as f:
            content = json.load(f)

        # read the parameters
        dcs_name = parameters["district_cooling_system"]
        cluster_name = parameters["cluster"]
        building_footprints = parameters["building_footprints"]

        # generate system summary bar chart
        summary_charts = create_system_summary_charts(content['DCS'], dcs_name)

        # generate network map
        network_map = create_network_map(content['DCS'][dcs_name][cluster_name]['network'], dcs_name, cluster_name)

        # generate connected building map
        connected_building_map = create_connected_building_map(network_map, building_footprints)

        # generate pie charts
        pie_charts = create_pie_charts(content['DCS'][dcs_name][cluster_name]['structure'])

        # generate a flow chart
        # flow_chart = create_network_flow_chart(content['DCS'][dcs_name][cluster_name]['structure'])

        return [
            network_map,
            connected_building_map,
            *summary_charts,
            *pie_charts,
            # flow_chart
        ]

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> dict:
        raise NotImplemented()

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        if export_format == 'json':
            shutil.copyfile(content_path, export_path)
        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        if export_format == 'json':
            raise NotImplemented()
        else:
            raise DUCTRuntimeError(f"Format not supported for export: {export_format}")