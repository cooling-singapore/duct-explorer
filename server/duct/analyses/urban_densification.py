import json
import math
from typing import List, Dict, Tuple

import numpy as np
import rasterio
from pyproj import CRS
from rasterio.features import rasterize

from duct.dots import duct
from saas.sdk.base import SDKContext, SDKCDataObject, SDKProductSpecification

from duct.exceptions import DUCTRuntimeError
from explorer.analysis.base import Analysis, AnalysisContext, AnalysisStatus
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import AnalysisGroup, Scene, AnalysisResult, ExplorerRuntimeError, AnalysisSpecification

import geopandas as gpd


def get_geojson_property_range(geojson: dict, property_name: str) -> Tuple[int, int]:
    return (
        max((f["properties"][property_name] for f in geojson["features"] if f["properties"][property_name] is not None),
            default=0),
        min((f["properties"][property_name] for f in geojson["features"] if f["properties"][property_name] is not None),
            default=0)
    )


def generate_2d_building_map_spec(title: str, field: str, units: str, geojson: Dict) -> Dict:
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
                "type": "simple-fill",
                "outline": {
                    "color": [
                        1,
                        1,
                        1
                    ],
                    "width": 0.5
                }
            },
            "label": "Buildings",
            "visualVariables": [
                {
                    "type": "color",
                    "field": field,
                    "legendOptions": {
                        "title": f"{title} ({units})"
                    },
                    "stops": [
                        {
                            "value": _range[0],
                            "color": "#350242",
                            "label": _range[0]
                        },
                        {
                            "value": _range[1],
                            "color": "#FFFCD4",
                            "label": _range[1]
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
                            "fieldName": "name",
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
                    "expression": 'DefaultValue($feature.name, "Unknown")'
                },
                "minScale": 2500
            }
        ],
        "geojson": geojson
    }


class UrbanDensification(Analysis):
    def name(self) -> str:
        return "urban-densification"

    def label(self) -> str:
        return "Urban Densification"

    def type(self) -> str:
        return 'meso'

    def specification(self, project, sdk: SDKContext, aoi_obj_id: str = None,
                      scene_id: str = None) -> AnalysisSpecification:
        return AnalysisSpecification.parse_obj({
            "name": self.name(),
            "label": self.label(),
            "type": self.type(),
            "area_selection": False,
            "parameters_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "title": "Configuration Name"},
                    "use_data": {"type": "boolean", "title": "Use measured data", "default": True}
                },
                "required": ["name", "use_data"],
            },
            "description": "This analysis estimates the changes of energy consumption from buildings due to "
                           "densification, using population projections for 2050. "
                           "The scenario being considered is verticalization, where a uniform growth is "
                           "applied to all buildings, assuming an increase of GFA while keeping a constant footprint "
                           "area. GFA growth estimations are based mainly on population growth using data from UN "
                           "estimations and past growth. Energy consumption is estimated using EUI from historical "
                           "measured data (2019) or generated based on some statistics.",
            "further_information": "This analysis is based on a model developed by "
                                   "<a href='mailto:luis.santos@tum-create.edu.sg'>Luis Santos</a>. "
                                   "The SaaS adaptor for this model has been developed by "
                                   "<a href='mailto:reynold.mok@sec.ethz.ch'>Reynold Mok</a>. "
                                   "For more information, please contact the respective authors.",
            "sample_image": self.name()+'.png',
            "ui_schema": {},
            "required_processors": ["ude-sim"],
            "required_bdp": [],
            "result_specifications": {}
        })

    def _generate_raster_from_dataframe(self, geometries: gpd.GeoDataFrame, values: np.ndarray,
                                        output_path: str) -> None:
        minx, miny, maxx, maxy = geometries.total_bounds
        grid_bounds = geometries.iloc[0].bounds

        # Figure out grid shape from bounds
        rows = math.ceil((maxy.max() - miny.min()) / (grid_bounds[3] - grid_bounds[1]))
        cols = math.ceil((maxx.max() - minx.min()) / (grid_bounds[2] - grid_bounds[0]))

        arr = list(zip(geometries.values, values.tolist()))
        transform = rasterio.transform.from_bounds(minx, miny, maxx, maxy, cols, rows)
        raster = rasterize(
            arr,
            transform=transform,
            out_shape=(rows, cols),
            fill=-1
        )

        with rasterio.open(output_path, 'w',
                           driver='GTiff',
                           height=rows, width=cols,
                           count=1, dtype=values.dtype,
                           nodata=-1,
                           crs=CRS.from_epsg(4326),
                           transform=transform) as dst:
            dst.write(raster, 1)

    def _run_sim_job(self, context: AnalysisContext,
                     building_footprints: SDKCDataObject, parameters: Dict) -> Dict[str, SDKCDataObject]:
        proc_name = 'ude-sim'
        # find the processor
        proc = context.sdk.find_processor_by_name(proc_name)
        if proc is None:
            raise DUCTRuntimeError(f"Processor '{proc_name}' not found.")

        # submit the job
        inputs = {
            'building-footprints': building_footprints,
            'parameters': parameters,
        }

        outputs = {
            name: SDKProductSpecification(
                restricted_access=False,
                content_encrypted=False,
                target_node=context.sdk.dor()
            ) for name in ['densified-building-footprints', 'heatmap-grid']
        }

        job = proc.submit(inputs, outputs,
                          name=f"{context.analysis_id}.0",
                          description=f"job part of analysis {context.analysis_id}")
        context.add_update_tracker(f'job:{job.content.id}', 100)
        data_objs = job.wait(callback_progress=lambda x: context.update_progress(f'job:{job.content.id}', x),
                             callback_message=context.update_message)

        return data_objs

    def perform_analysis(self, group: AnalysisGroup, scene: Scene, context: AnalysisContext) -> List[AnalysisResult]:
        self_tracker_name = 'ude.perform_analysis'
        context.add_update_tracker(self_tracker_name, 10)

        checkpoint, args, status = context.update_checkpoint('run-sim-job', {
            'use_data': group.parameters["use_data"],
            'building_footprints_id': context.bld_footprint_obj_id()
        })

        if status == AnalysisStatus.RUNNING and checkpoint == 'run-sim-job':
            context.update_progress(self_tracker_name, 20)

            building_footprints = context.sdk.find_data_object(args['building_footprints_id'])
            parameters = {
                'use_data': bool(args['use_data'])
            }

            outputs = self._run_sim_job(context, building_footprints, parameters)

            checkpoint, args, status = context.update_checkpoint('simulation-done', {
                name: obj.meta.obj_id for name, obj in outputs.items()
            })

        if status == AnalysisStatus.RUNNING and checkpoint == 'simulation-done':
            context.update_progress(self_tracker_name, 80)

            densified_building_footprints = args['densified-building-footprints']
            heatmap_grid = args['heatmap-grid']

            # prepare analysis results
            results = [
                AnalysisResult.parse_obj({
                    'name': 'mean_heat_flux',
                    'obj_id': {'#': heatmap_grid},
                    'label': 'Mean Heat Flux Heatmap',
                    'specification': {
                        'description': 'Mean heat flux (W/m2) delta in 300m grid resolution.',
                        'parameters': {}
                    },
                    'export_format': 'tiff',
                    'extras': {}
                }),
                AnalysisResult.parse_obj({
                    'name': 'annual_energy_consumption',
                    'obj_id': {'#': heatmap_grid},
                    'label': 'Annual Energy Consumption Heatmap',
                    'specification': {
                        'description': 'Annual Energy Consumption (MWh) delta in 300m grid resolution.',
                        'parameters': {}
                    },
                    'export_format': 'tiff',
                    'extras': {}
                }),
                AnalysisResult.parse_obj({
                    'name': 'annual_energy_consumption_building_footprints',
                    'obj_id': {'#': densified_building_footprints},
                    'label': 'Annual Energy Consumption Building Footprints',
                    'specification': {
                        'description': 'Indicates delta of energy consumption (MWh) per building.',
                        'parameters': {}
                    },
                    'export_format': 'geojson',
                    'extras': {}
                })
            ]

            # update the progress tracker for this function
            context.update_progress(self_tracker_name, 100)
            return results

        if status != AnalysisStatus.CANCELLED:
            raise DUCTRuntimeError(f"Encountered unexpected checkpoint: {checkpoint}")

    def extract_feature(self, content_paths: Dict[str, str], result: AnalysisResult, parameters: dict,
                        project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:
        if result.name == 'annual_energy_consumption_building_footprints':
            field = "d_Ec_MWh"

            df = gpd.read_file(content_paths['#'])[[field, "geometry"]].round()
            densified_building_footprints = json.loads(df.to_json())

            with open(json_path, 'w') as f:
                assets = [generate_2d_building_map_spec(
                    title="Energy Consumption Delta",
                    field=field,
                    units="MWh",
                    geojson=densified_building_footprints
                )]
                f.write(json.dumps(assets))

            if result.export_format == 'geojson':
                with open(export_path, 'w') as f:
                    json.dump(densified_building_footprints, f)
            else:
                raise DUCTRuntimeError(f"Format not supported for export: {result.export_format}")

        if result.name == 'mean_heat_flux':
            field = "d_ED_tot_Wh/m2"

            parameters['legend_title'] = "Mean Heat Flux Delta (W/m2)"
            parameters['no_data'] = -1

            df = gpd.read_file(content_paths['#'])
            values = df[field].round(2)

            # Bin values based on range
            bins = [0.0, 0.01, 0.1, 1, 10, 100, 1000]
            binned = np.digitize(values, bins)

            raster_path = content_paths['#'] + ".tiff"
            self._generate_raster_from_dataframe(df.geometry, binned, raster_path)

            parameters['color_schema'] = [
                {'value': 1, 'color': hex_color_to_components('#1C9741'), 'label': '0 - 0.01'},
                {'value': 2, 'color': hex_color_to_components('#8BCB67'), 'label': '0.01 - 0.1'},
                {'value': 3, 'color': hex_color_to_components('#DAF19A'), 'label': '0.1 - 1'},
                {'value': 4, 'color': hex_color_to_components('#FBE09A'), 'label': '1 - 10'},
                {'value': 5, 'color': hex_color_to_components('#F59053'), 'label': '10 - 100'},
                {'value': 6, 'color': hex_color_to_components('#D51919'), 'label': '100 - 1,000'}
            ]

            # Change heat map type to discrete
            heat_map_feature = duct.GeoRasterData().extract_feature(raster_path, parameters)
            heat_map_feature['subtype'] = "discrete"

            with open(json_path, 'w') as f:
                assets = [heat_map_feature]
                f.write(json.dumps(assets))

            duct.GeoRasterData().export_feature(raster_path, parameters, export_path, result.export_format)

        if result.name == 'annual_energy_consumption':
            field = "d_Ec_tot_MWh"

            parameters['legend_title'] = "Annual Energy Consumption Heatmap (MWh)"
            parameters['no_data'] = -1

            df = gpd.read_file(content_paths['#'])
            values = df[field].round(1)

            # Bin values based on range
            bins = [0, 10, 100, 1000, 10000, 100000, 1000000]
            binned = np.digitize(values, bins)

            raster_path = content_paths['#'] + ".tiff"
            self._generate_raster_from_dataframe(df.geometry, binned, raster_path)

            parameters['color_schema'] = [
                {'value': 1, 'color': hex_color_to_components('#1C9741'), 'label': '0 - 10'},
                {'value': 2, 'color': hex_color_to_components('#8BCB67'), 'label': '10 - 100'},
                {'value': 3, 'color': hex_color_to_components('#DAF19A'), 'label': '100 - 1,000'},
                {'value': 4, 'color': hex_color_to_components('#FBE09A'), 'label': '1,000 - 10,000'},
                {'value': 5, 'color': hex_color_to_components('#F59053'), 'label': '10,000 - 100,000'},
                {'value': 6, 'color': hex_color_to_components('#D51919'), 'label': '100,000 - 1,000,000'}
            ]

            # Change heat map type to discrete
            heat_map_feature = duct.GeoRasterData().extract_feature(raster_path, parameters)
            heat_map_feature['subtype'] = "discrete"

            with open(json_path, 'w') as f:
                assets = [heat_map_feature]
                f.write(json.dumps(assets))

            duct.GeoRasterData().export_feature(raster_path, parameters, export_path, result.export_format)

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result.name}'", details={
                'result': result.dict(),
                'parameters': parameters
            })

    def extract_delta_feature(self, content_paths0: Dict[str, str], result0: AnalysisResult, parameters0: dict,
                              content_paths1: Dict[str, str], result1: AnalysisResult, parameters1: dict,
                              project: Project, sdk: SDKContext, export_path: str, json_path: str) -> None:
        # check if the result names are identical
        if result0.name != result1.name:
            raise DUCTRuntimeError(f"Mismatching result names: {result0.name} != {result1.name}")

        if result0.name == 'densified_building_footprints':
            a = gpd.read_file(content_paths0)
            b = gpd.read_file(content_paths0)

            field = 'd_Ec_MWh'
            a['delta'] = a[field] - b[field]
            delta = a[['delta']].to_dict()

            with open(json_path, 'w') as f:
                assets = [generate_2d_building_map_spec(
                    title="Energy Consumption Delta",
                    field='delta',
                    units="MWh",
                    geojson=delta
                )]
                f.write(json.dumps(assets))

            if result0.export_format == 'geojson':
                with open(export_path, 'w') as f:
                    json.dump(delta, f)
            else:
                raise DUCTRuntimeError(f"Format not supported for export: {result0.export_format}")

        if result0.name == 'heatmap_grid':
            a = gpd.read_file(content_paths0)
            b = gpd.read_file(content_paths0)

            field = 'd_ED_tot_Wh/m2'
            a['delta'] = a[field] - b[field]
            delta = a[['delta']].to_dict()

            with open(json_path, 'w') as f:
                assets = [generate_2d_building_map_spec(
                    title="Mean Heat Flux Delta",
                    field="delta",
                    units="Wh/m2",
                    geojson=delta
                )]
                f.write(json.dumps(assets))

            if result0.export_format == 'geojson':
                with open(export_path, 'w') as f:
                    json.dump(delta, f)
            else:
                raise DUCTRuntimeError(f"Format not supported for export: {result0.export_format}")

        else:
            raise ExplorerRuntimeError(f"Encountered unexpected/unsupported result '{result0.name}'/'{result1.name}'",
                                       details={
                                           'result0': result0.dict(),
                                           'result1': result1.dict(),
                                           'parameters0': parameters0,
                                           'parameters1': parameters1
                                       })
