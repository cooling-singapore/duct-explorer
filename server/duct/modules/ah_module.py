import json
import os
import pickle
from typing import List, Tuple, Optional, Dict

import numpy as np
from saas.core.logging import Logging

from duct.analyses.microscale_urban_climate import coord_4326_to_32648
from saas.sdk.base import SDKContext

from duct.dots.duct_ahprofile import AnthropogenicHeatProfile
from duct.renderer.ah_profile_renderer import AHProfileRenderer
from explorer.module.base import BuildModule
from explorer.project import Project
from explorer.schemas import BuildModuleSpecification, BoundingBox, ExplorerRuntimeError

logger = Logging.get('duct.modules.ah')


def grid_overlap(feature: dict, bbox: BoundingBox, d_lat: float, d_lon: float) -> List[Tuple[int, int]]:
    if feature['geometry']['type'] == 'LineString':
        p0 = feature['geometry']['coordinates'][0]
        p1 = feature['geometry']['coordinates'][1]

        y0, x0 = int((bbox.north - p0[1]) / d_lat), int((p0[0] - bbox.west) / d_lon)
        y1, x1 = int((bbox.north - p1[1]) / d_lat), int((p1[0] - bbox.west) / d_lon)

        # how many steps?
        ay = abs(y1 - y0)
        ax = abs(x1 - x0)
        n = max(ay, ax)

        result = []
        if n == 0:
            result.append((y0, x0))

        elif n == 1:
            result.append((y0, x0))
            result.append((y1, x1))

        else:
            # determine lon/lat steps size
            dlon = (p1[0] - p0[0]) / n
            dlat = (p1[1] - p0[1]) / n
            for i in range(0, n + 1, 1):
                lat = p0[1] + i * dlat
                lon = p0[0] + i * dlon

                y = int((bbox.north - lat) / d_lat)
                x = int((lon - bbox.west) / d_lon)

                result.append((y, x))

        return result

    elif feature['geometry']['type'] == 'Point':
        p = feature['geometry']['coordinates']
        y, x = int((bbox.north - p[1]) / d_lat), int((p[0] - bbox.west) / d_lon)
        return [(y, x)]

    else:
        raise ExplorerRuntimeError(f"Unsupported geometry type: '{feature['geometry']['type']}'")


def find_and_rasterise(obj_id: str, project: Project, sdk: SDKContext) -> np.ndarray:
    # do we already have the 24 raster stack?
    raster_path = os.path.join(project.info.temp_path, f"{obj_id}_24ah_stack.ndarray")
    if os.path.isfile(raster_path):
        with open(raster_path, 'rb') as file:
            loaded_data = file.read()
            raster_stack = pickle.loads(loaded_data)
            return raster_stack

    # find the data object
    content_path = os.path.join(project.info.temp_path, f"{obj_id}_ah.geojson")
    obj = sdk.find_data_object(obj_id)
    if obj:
        # download the data object
        obj.download(content_path)

        # read the content
        with open(content_path, 'r') as f:
            content: dict = json.loads(f.read())

        os.remove(content_path)

    else:
        logger.error(f"AH profile {obj_id} not found in DOR -> using 'no data' as default")

        content = {
            'type': 'FeatureCollection',
            'features': []
        }

    # determine raster dimensions
    height = project.info.bdp.grid_dimension.height
    width = project.info.bdp.grid_dimension.width

    # determine lat/lon resolutions
    bounding_box = project.info.bdp.bounding_box
    d_lat = (bounding_box.north - bounding_box.south) / height
    d_lon = (bounding_box.east - bounding_box.west) / width

    # create 24 raster, one for each hour of the day
    all_raster = [np.zeros(shape=(height, width), dtype=np.float32) for _ in range(24)]

    # for each feature, normalise AH determine the max AH for each feature and overall max AH
    multipliers = {'MW': 1e6, 'KW': 1e3, 'W': 1}
    for feature in content['features']:
        for key, value in feature['properties'].items():
            if key.startswith("AH_") and key != 'AH_type':
                if value > 0:
                    # determine hour of the day and the unit
                    temp = key.replace(' ', '')  # example key: "AH_0:MW"
                    temp = temp[3:]  # "AH_0:MW" -> "0:MW"
                    temp = temp.split(":")  # "0:MW" -> ["0", "MW"]
                    hour = int(temp[0])
                    unit = temp[1]

                    # normalise AH value to Watts
                    m = multipliers.get(unit)
                    ah = value * m  # [W]

                    # determine the coordinates of cells over which AH should be distributed
                    cells = grid_overlap(feature, bounding_box, d_lat, d_lon)

                    # divide the AH by the number of cells, so the overall AH for this feature
                    # is equally spread across all cells.
                    d_ah = ah / len(cells)

                    # spread the AH to the relevant cells
                    raster = all_raster[hour]
                    for cell in cells:
                        y = cell[0]
                        x = cell[1]
                        if 0 <= y < height and 0 <= x < width:
                            raster[y][x] += d_ah

    # stack the 24 raster and serialise
    raster_stack: np.ndarray = np.stack(all_raster, axis=0)
    with open(raster_path, 'wb') as file:
        serialized_data = pickle.dumps(raster_stack)
        file.write(serialized_data)

    return raster_stack


def find_and_discretise(obj_id: str, project: Project, sdk: SDKContext,
                        default_ah_type: str) -> Dict[int, Tuple[np.ndarray, np.ndarray]]:
    # find the data object
    content_path = os.path.join(project.info.temp_path, f"{obj_id}_ah.geojson")
    obj = sdk.find_data_object(obj_id)
    if obj:
        # download the data object
        obj.download(content_path)

        # read the content
        with open(content_path, 'r') as f:
            content: dict = json.loads(f.read())

        os.remove(content_path)

    else:
        logger.error(f"AH profile {obj_id} not found in DOR -> using 'no data' as default")

        content = {
            'type': 'FeatureCollection',
            'features': []
        }

    # determine raster dimensions
    height = project.info.bdp.grid_dimension.height
    width = project.info.bdp.grid_dimension.width

    # determine lat/lon resolutions
    bounding_box = project.info.bdp.bounding_box
    d_lat = (bounding_box.north - bounding_box.south) / height
    d_lon = (bounding_box.east - bounding_box.west) / width

    # for each feature, normalise AH to [W]
    result: Dict[int, (np.ndarray, np.ndarray)] = {}
    multipliers = {'GW': 1e9, 'MW': 1e6, 'KW': 1e3, 'W': 1}
    for feature in content['features']:
        # determine the z-value, i.e., height in meters
        z = feature['properties']['height:m']
        if z not in result:
            result[z] = (np.zeros((height, width, 24)), np.zeros((height, width, 24)))  # (sh, lh)
        sh_raster_at_z, lh_raster_at_z = result[z]

        # determine if SH or LH --> use default AH type if property not found
        ah_type = feature['properties']['AH_type'] if 'AH_type' in feature['properties'] else default_ah_type
        raster_at_z = lh_raster_at_z if ah_type == 'LH' else sh_raster_at_z

        for key, value in feature['properties'].items():
            if key != 'AH_type' and key.startswith("AH_") and value > 0:
                # determine hour of the day and the unit
                temp = key.replace(' ', '')  # example key: "AH_0:MW"
                temp = temp[3:]  # "AH_0:MW" -> "0:MW"
                temp = temp.split(":")  # "0:MW" -> ["0", "MW"]
                hour = int(temp[0])
                unit = temp[1]

                # determine the coordinates of cells over which AH should be distributed
                cells = grid_overlap(feature, bounding_box, d_lat, d_lon)

                # normalise AH value to Watts per cell
                m = multipliers.get(unit)
                ah = value * m  # [W]
                ah = ah / len(cells)

                # create an item and add to the result
                for cell in cells:
                    y = cell[0]
                    x = cell[1]

                    if 0 <= y < height and 0 <= x < width:
                        raster_at_z[y, x, hour] = raster_at_z[y, x, hour] + ah

    return result


def raster_to_geojson(raster: np.ndarray, project: Project, title: str,
                      show_outline: bool = False, global_max_ah: Optional[int] = None) -> dict:
    # determine raster dimensions
    height = project.info.bdp.grid_dimension.height
    width = project.info.bdp.grid_dimension.width

    # determine lat/lon resolutions
    bounding_box = project.info.bdp.bounding_box
    d_lat = (bounding_box.north - bounding_box.south) / height
    d_lon = (bounding_box.east - bounding_box.west) / width

    # determine the area of a cell
    p0 = coord_4326_to_32648((bounding_box.west, bounding_box.north))
    p1 = coord_4326_to_32648((bounding_box.west+d_lon, bounding_box.north+d_lat))
    dx = p0[0] - p1[0]  # distance in [m]
    dy = p0[1] - p1[1]  # distance in [m]
    area = dx * dy  # in [m^2]

    # iterate over all non-zero cells
    features = []
    non_zero_coords = np.transpose(np.nonzero(raster))
    local_max_ah = 0
    for coord in non_zero_coords:
        # turn [W] into [W/m^2]
        ah_value = raster[coord[0], coord[1]]
        ah_value = int(ah_value / area)
        if ah_value > local_max_ah:
            local_max_ah = ah_value

        lat0 = round(bounding_box.north - coord[0] * d_lat, 4)
        lat1 = round(lat0 - d_lat, 4)

        lon0 = round(bounding_box.west + coord[1] * d_lon, 4)
        lon1 = round(lon0 + d_lon, 4)

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]]
            },
            "properties": {
                "AH_value": ah_value
            }
        })

    # which max AH to use?
    max_ah = global_max_ah if global_max_ah else local_max_ah

    ah_profile_renderer = AHProfileRenderer()

    return {
        "type": "geojson",
        "title": title,
        "geojson": {
            "type": "FeatureCollection",
            "features": features
        },
        "renderer": ah_profile_renderer.renderer(title,
                                                 "AH_value",
                                                 "Anthropogenic (Sensible+Latent) Heat Emissions (in Watts per square meter)",
                                                 False)
    }

def export_raster_to_geojson(raster_by_z: Dict[int, np.ndarray], output_path: str, ah_type: str,
                             project: Project) -> None:
    # determine raster dimensions
    height = project.info.bdp.grid_dimension.height
    width = project.info.bdp.grid_dimension.width

    # determine lat/lon resolutions
    bounding_box = project.info.bdp.bounding_box
    d_lat = (bounding_box.north - bounding_box.south) / height
    d_lon = (bounding_box.east - bounding_box.west) / width

    # generate point features for every non-zero AH cell
    features = []
    for z, raster in raster_by_z.items():
        for j in range(raster.shape[0]):
            lat = bounding_box.north - j * d_lat - d_lat/2

            for i in range(raster.shape[1]):
                lon = bounding_box.west + i * d_lon + d_lon / 2

                # check if there is any non-zero AH value in this cell -> if not, skip
                ah_sum = np.sum(raster[j, i])
                if ah_sum == 0:
                    continue

                # build the properties
                properties = {
                    "AH_type": ah_type,
                    'height:m': z
                }

                for h in range(24):
                    properties[f"AH_{h}:W"] = int(raster[j, i, h])

                features.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat]
                    },
                    "properties": properties
                })

    # create AH profile GeoJSON with point sources --> that's fine because WRF is anyway going to raster the AH
    # information.
    with open(output_path, 'w') as f:
        json.dump({
            "type": "FeatureCollection",
            "features": features
        }, f)


def export_traffic(p_ev: float, output_path: str, project: Project, sdk: SDKContext) -> None:
    # determine the fraction of EV
    p_ev = 0.0 if p_ev < 0 else p_ev
    p_ev = 1.0 if p_ev > 1 else p_ev
    q_ev = 1.0 - p_ev

    obj_id0 = project.info.bdp.references['sh-traffic-baseline']
    obj_id1 = project.info.bdp.references['sh-traffic-ev100']

    raster_by_z0 = find_and_discretise(obj_id0, project, sdk, 'SH')
    raster_by_z1 = find_and_discretise(obj_id1, project, sdk, 'SH')

    # assuming z is the same for both!
    raster_by_z = {}
    for z in raster_by_z0.keys():
        # traffic shouldn't have any LH -> so we ignore it
        raster0, _ = raster_by_z0.get(z)
        raster1, _ = raster_by_z1.get(z)

        # determine the AH raster determine on EV fraction
        raster = q_ev * raster0 + p_ev * raster1

        raster_by_z[z] = raster

    # export the rasters as GeoJSON with Point geometries
    export_raster_to_geojson(raster_by_z, output_path, 'SH', project)


def export_power(base_demand: float, ev100_demand: float, p_ev: float, p_demand: float, renewables: float,
                 imports: float, sh_output_path: str, lh_output_path: str, project: Project, sdk: SDKContext) -> None:
    p_ev = 0.0 if p_ev < 0 else p_ev
    p_ev = 1.0 if p_ev > 1 else p_ev

    # what is the demand of the scenario? --> the original base demand x expected change (in %) + EV demand (if any).
    scenario_demand = (base_demand * p_demand) + (ev100_demand * p_ev)

    # how much of the scenario demand needs to be supplied by Domestic Non-Renewables (DNR)? <-- that's the processes
    # that emit anthropogenic heat. basically: because supply must meet demand, therefore DNR supply is scenario demand
    # minus renewables and imports.
    dnr_supply = scenario_demand - renewables - imports

    # what is the fraction of DNR supply in terms of base demand? <-- assumption here is that if we only need to
    # produce, say, 80% compared to the current base demand (maybe because assumption is energy consumption goes down),
    # then we also only emit 80% of the current anthropogenic heat emissions. in other words we can use this fraction
    # as a scaling factor for power plant AH emissions.
    s = dnr_supply / base_demand

    # get power plant baseline emissions (SH and LH) and rasterise them
    obj_id_sh = project.info.bdp.references['sh-power-baseline']
    obj_id_lh = project.info.bdp.references['lh-power-baseline']

    # obtain the baseline emission raster --> since it's in dedicated files, we can ignore the SH/LH portion of
    # each of the two find and discretise results accordingly.
    raster_by_sh0 = find_and_discretise(obj_id_sh, project, sdk, 'SH')
    raster_by_lh0 = find_and_discretise(obj_id_lh, project, sdk, 'LH')

    # scale the baseline by s to obtain the scenario SH/LH
    raster_by_sh1 = {key: s * raster[0] for key, raster in raster_by_sh0.items()}
    raster_by_lh1 = {key: s * raster[1] for key, raster in raster_by_lh0.items()}

    # export the rasters as GeoJSON with Point geometries
    export_raster_to_geojson(raster_by_sh1, sh_output_path, 'SH', project)
    export_raster_to_geojson(raster_by_lh1, lh_output_path, 'LH', project)


def export_others(ohe_obj_id: str, sh_output_path: str, lh_output_path: str, project: Project, sdk: SDKContext) -> None:
    if ohe_obj_id:
        raster_by_z = find_and_discretise(ohe_obj_id, project, sdk, 'SH')

        raster_by_z_sh = {k: raster[0] for k, raster in raster_by_z.items()}
        raster_by_z_lh = {k: raster[1] for k, raster in raster_by_z.items()}

        # export the rasters as GeoJSON with Point geometries
        export_raster_to_geojson(raster_by_z_sh, sh_output_path, 'SH', project)
        export_raster_to_geojson(raster_by_z_lh, lh_output_path, 'LH', project)
    else:
        # without an object id, just create two empty feature collections for SH and LH
        feature_collection = {"type": "FeatureCollection", "features": []}

        with open(sh_output_path, 'w') as f:
            json.dump(feature_collection, f)

        with open(lh_output_path, 'w') as f:
            json.dump(feature_collection, f)


def heatmap_traffic(p_ev: float, t: int, project: Project, sdk: SDKContext) -> np.ndarray:
    # determine the fraction of EV
    p_ev = 0.0 if p_ev < 0 else p_ev
    p_ev = 1.0 if p_ev > 1 else p_ev
    q_ev = 1.0 - p_ev

    obj_id0 = project.info.bdp.references['sh-traffic-baseline']
    obj_id1 = project.info.bdp.references['sh-traffic-ev100']

    raster0: np.ndarray = find_and_rasterise(obj_id0, project, sdk)
    raster1: np.ndarray = find_and_rasterise(obj_id1, project, sdk)

    raster0: np.ndarray = raster0[t]
    raster1: np.ndarray = raster1[t]

    # determine the AH raster determine on EV fraction
    raster = q_ev * raster0 + p_ev * raster1
    return raster


def heatmap_power(base_demand: float, ev100_demand: float, p_ev: float, p_demand: float, renewables: float,
                  imports: float, t: int, project: Project, sdk: SDKContext) -> np.ndarray:

    p_ev = 0.0 if p_ev < 0 else p_ev
    p_ev = 1.0 if p_ev > 1 else p_ev

    # what is the demand of the scenario? --> the original base demand x expected change (in %) + EV demand (if any).
    scenario_demand = (base_demand * p_demand) + (ev100_demand * p_ev)

    # how much of the scenario demand needs to be supplied by Domestic Non-Renewables (DNR)? <-- that's the processes
    # that emit anthropogenic heat. basically: because supply must meet demand, therefore DNR supply is scenario demand
    # minus renewables and imports.
    dnr_supply = scenario_demand - renewables - imports

    # what is the fraction of DNR supply in terms of base demand? <-- assumption here is that if we only need to
    # produce, say, 80% compared to the current base demand (maybe because assumption is energy consumption goes down),
    # then we also only emit 80% of the current anthropogenic heat emissions. in other words we can use this fraction
    # as a scaling factor for power plant AH emissions.
    s = dnr_supply / base_demand

    # get power plant baseline emissions (SH and LH) and rasterise them
    obj_id_sh = project.info.bdp.references['sh-power-baseline']
    obj_id_lh = project.info.bdp.references['lh-power-baseline']
    raster_sh: np.ndarray = find_and_rasterise(obj_id_sh, project, sdk)
    raster_lh: np.ndarray = find_and_rasterise(obj_id_lh, project, sdk)

    # extract the one for the time of interest at time t
    raster_sh: np.ndarray = raster_sh[t]
    raster_lh: np.ndarray = raster_lh[t]

    # combine SH and LH to obtain total AH --> we are making an assumption here: that SH and LH scale in equal
    # terms, i.e., if overall AH increases by x% then that means equal raise in SH and LH by x%.
    raster: np.ndarray = raster_sh + raster_lh

    # for the given scenario: the baseline AH emissions x the scaling factor calculated above
    raster = raster * s

    return raster


def heatmap_others(ohe_obj_id: str, t: int, project: Project, sdk: SDKContext) -> np.ndarray:
    # find and rasterise the OHE emissions
    raster: np.ndarray = find_and_rasterise(ohe_obj_id, project, sdk)

    # extract the one for the time of interest at time t
    raster: np.ndarray = raster[t]

    return raster


class AnthropogenicHeatModule(BuildModule):
    def name(self) -> str:
        return 'anthropogenic-heat'

    def label(self) -> str:
        return 'Anthropogenic Heat'

    def type(self) -> str:
        return 'meso'

    def specification(self, project: Project) -> BuildModuleSpecification:
        ah_obj_id = ['']
        ah_labels = ['(none)']
        for dataset in project.info.datasets.values():
            if dataset.type == AnthropogenicHeatProfile.DATA_TYPE:
                ah_obj_id.append(dataset.obj_id)
                ah_labels.append(dataset.name)

        return BuildModuleSpecification.parse_obj({
            'name': self.name(),
            'label': self.label(),
            'type': self.type(),
            'priority': 103,
            'description': 'This feature allow users to explore scenarios concerning traffic, power and other '
                           'significant sources of anthropogenic heat on the urban climate.',
            'parameters_schema': {
                "type": "object",
                "properties": {
                    "demand_chart": {
                        "type": "object"
                    },
                    "baseline": {
                        "type": "object",
                        "title": "",
                        "description": "Baseline"
                    },
                    "base_demand": {
                        "title": "Total annual electricity demand (GWh)",
                        "description": "",
                        "type": "integer",
                        "default": 48623
                    },
                    "projected_electricity_demand_change": {
                        "type": "object",
                        "title": "",
                        "description": "Projected change in electricity demand"
                    },
                    "ev100_demand": {
                        "title": "Electric vehicle (GWh)",
                        "description": "",
                        "type": "string",
                        "pattern": "^\\d+$",
                        "default": 2300
                    },
                    "p_demand": {
                        "title": "Change in general electricity demand (%)",
                        "description": "",
                        "type": "integer",
                        "min": -50,
                        "max": 50,
                        "step": 1,
                        "default": 0,
                        "defaultValue": 0,
                        "marks": [
                            {
                                "value": -50,
                                "label": "-50"
                            },
                            {
                                "value": 0,
                                "label": "0"
                            },
                            {
                                "value": 50,
                                "label": "50"
                            }
                        ]
                    },
                    "p_ev": {
                        "title": "Electric vehicles share",
                        "description": "",
                        "type": "integer",
                        "min": 0,
                        "max": 100,
                        "step": 1,
                        "default": 0,
                        "defaultValue": 0,
                        "marks": [
                            {
                                "value": 0,
                                "label": "0"
                            },
                            {
                                "value": 100,
                                "label": "100%"
                            }
                        ]
                    },
                    'others': {
                        'type': 'string',
                        'title': 'Other heat emission profiles',
                        'enum': ah_obj_id,
                        'enumNames': ah_labels,
                        'default': ah_obj_id[0]
                    },
                    "projected_supply": {
                        "type": "object",
                        "title": "",
                        "description": "Projected Supply"
                    },
                    "renewables": {
                        "title": "Generation of electricity by renewables(GWh)",
                        "description": "",
                        "type": "integer",
                        "default": 0
                    },
                    "imports": {
                        "title": "Import of Electricity (GWh)",
                        "description": "",
                        "type": "integer",
                        "default": 0
                    },
                    "time": {
                        "title": "Display Time of Day (in hours)",
                        "description": "",
                        "type": "integer",
                        "min": 0,
                        "max": 23,
                        "step": 1,
                        "default": 0,
                        "defaultValue": 0,
                        "marks": [
                            {"value": 0, "label": "0h"},
                            {"value": 3, "label": "3h"},
                            {"value": 6, "label": "6h"},
                            {"value": 9, "label": "9h"},
                            {"value": 12, "label": "12h"},
                            {"value": 15, "label": "15h"},
                            {"value": 18, "label": "18h"},
                            {"value": 21, "label": "21h"}
                        ]
                    }
                }
            },
            'has_raster_map': True,
            'has_update_map': False,
            'has_area_selector': False,
            'hide_settings_accordion': False,
            'editable': False,
            'editorConfig': {},
            'ui_schema': {
                'ui:order': ['demand_chart', 'baseline', 'base_demand', 'projected_electricity_demand_change',
                             'ev100_demand', 'p_demand', 'p_ev', 'others', 'projected_supply', 'renewables',
                             'imports', 'time'],
                'p_demand': {
                    "ui:widget": 'rangeWidget'
                },
                'p_ev': {
                    'ui:widget': 'rangeWidget'
                },
                'time': {
                    "ui:widget": 'rangeWidget'
                },
                'demand_chart': {
                    'ui:field': 'demandChart',
                    'module_name': self.name()
                }
            },
            'icon': 'power.svg'
        })

    def raster_image(self, project: Project, parameters: dict, sdk: SDKContext) -> List[dict]:
        module_settings = parameters['module_settings'][self.name()]
        result = []

        # what time of day to display?
        t = module_settings['time']

        # calculate traffic plant layer
        p_ev = module_settings['p_ev'] / 100.0
        raster_traffic = heatmap_traffic(p_ev, t, project, sdk)

        # calculate power plant layer
        p_demand = (100 + module_settings['p_demand']) / 100.0
        base_demand = module_settings['base_demand']
        ev100_demand = module_settings['ev100_demand']
        renewables = module_settings['renewables']
        imports = module_settings['imports']
        raster_power = heatmap_power(base_demand, ev100_demand, p_ev, p_demand, renewables, imports, t, project, sdk)

        # calculate OHE layer(s)
        ohe_obj_id = module_settings['others']
        if ohe_obj_id:
            raster_others = heatmap_others(ohe_obj_id, t, project, sdk)
        else:
            raster_others = None

        geojson_power = raster_to_geojson(raster_power, project, "Power Plant AH Emissions")
        result.append(geojson_power)

        geojson_traffic = raster_to_geojson(raster_traffic, project, "Traffic AH Emissions")
        result.append(geojson_traffic)

        if raster_others is not None:
            geojson_others = raster_to_geojson(raster_others, project, "Other AH Emissions")
            result.append(geojson_others)

        return result

    def chart(self, project: Project, parameters: dict, sdk: SDKContext) -> dict:
        module_settings = parameters['module_settings'][self.name()]

        p_ev = module_settings['p_ev'] / 100.0
        p_demand = module_settings['p_demand'] / 100.0
        baseline_demand = module_settings['base_demand']
        ev100_demand = module_settings['ev100_demand']

        proj_base_demand = int(baseline_demand + baseline_demand * p_demand)
        proj_ev_demand = int(ev100_demand * p_ev)
        proj_total = proj_base_demand + proj_ev_demand

        proj_renewables = module_settings['renewables']
        proj_imports = module_settings['imports']
        proj_dnr = proj_total - proj_renewables - proj_imports

        return {
            'labels': ['Baseline (current)', 'Demand (projected)', 'Supply (projected)'],
            'datasets': [
                {
                    'label': 'Energy Demand without EV',
                    'data': [baseline_demand, proj_base_demand, 0],
                    'backgroundColor': '#385e91'
                },
                {
                    'label': 'Energy Demand for EVs',
                    'data': [0, proj_ev_demand, 0],
                    'backgroundColor': '#a1b2d1'
                },
                {
                    'label': 'Domestic Non-Renewables',
                    'data': [0, 0, proj_dnr],
                    'backgroundColor': '#a24342'
                },
                {
                    'label': 'Domestic Renewables',
                    'data': [0, 0, proj_renewables],
                    'backgroundColor': '#bc6867'
                },
                {
                    'label': 'Imports            ',
                    'data': [0, 0, proj_imports],
                    'backgroundColor': '#dda2a2'
                }
            ]
        }

