import json
import logging
import os
import shutil
import unittest

from typing import Tuple, List, Dict

from saas.core.keystore import Keystore
from saas.node import Node
from saas.sdk.base import connect
from tests.base_testcase import create_wd, PortMaster

from saas.core.logging import Logging

from duct.analyses.building_energy_efficiency import BuildingEnergyEfficiency
from duct.dots.duct_ahprofile import AnthropogenicHeatProfile
from duct.dots.duct_bemcea import aggregate_ah_data, BuildingAnnualEnergy, BuildingAnnualGeneration, \
    create_system_summary_charts, create_network_map, create_connected_building_map, create_pie_charts, \
    create_network_flow_chart
from duct.dots.duct_bld_eff_std import BuildingEfficiencyStandard
from duct.dots.duct_lcz import LocalClimateZoneMap
from duct.dots.duct_nsc_variables import extract_nsc_data, NearSurfaceClimateVariableLinechart, \
    NearSurfaceClimateVariableRaster
from duct.dots.duct_urban_geometries import UrbanGeometries
from explorer.dots.dot import UploadPostprocessResult
from explorer.geodb import GeometryType
from explorer.project import Project
from explorer.renderer.base import hex_color_to_components
from explorer.schemas import ProjectInfo, BaseDataPackage, BoundingBox, Dimensions, ProjectMeta, ZoneConfiguration

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')


class DUCTDOTTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_NearSurfaceClimateVariables(self):
        input_path = os.path.join(nextcloud_path, 'ucmwrf_sim', 'output', 'd04-near-surface-climate')
        dot = NearSurfaceClimateVariableRaster()
        datetime_0h = '20160417160000'

        export_path = os.path.join(self._wd_path, 'feature.tiff')
        export_format = 'tiff'
        parameters = {
            'key': '2m_air_temperature',
            'datetime_0h': datetime_0h,
            'time': 0,
            'no_data': 0,
            'legend_title': 'title',
            'color_schema': [
                {'value': 0, 'color': hex_color_to_components('#ffffff', 0), 'label': '-'},
                {'value': 1, 'color': hex_color_to_components('#dd1111', 192), 'label': 'Urban'},
            ]
        }

        dot.export_feature(input_path, parameters, export_path, export_format)
        assert(export_path)

        json = dot.extract_feature(input_path, parameters)
        assert(json is not None)

        export_path = os.path.join(self._wd_path, 'feature_delta.tiff')
        parameters_delta = {
            'A': {
                'key': '2m_air_temperature',
                'datetime_0h': datetime_0h,
                'time': 0,
            },
            'B': {
                'key': '2m_air_temperature',
                'datetime_0h': datetime_0h,
                'time': 0,
            },
            'common': {
                'no_data': 0,
                'legend_title': 'title',
                'color_schema': None
            }
        }
        dot.export_delta_feature(input_path, input_path, parameters_delta, export_path, export_format)
        assert(export_path)

        json = dot.extract_delta_feature(input_path, input_path, parameters_delta)
        assert(json is not None)

    # FIXME: the file doesn't seem to exist (anymore?) so the testcase is broken.
    # def test_DistrictNetworkFlowchart(self):
    #     components_structure = os.path.join(nextcloud_path, 'dcn-sim', 'output', 'N1001_supply_system_structure.csv')
    #     flow_chart = SupplySystems._create_network_flow_chart(pd.read_csv(components_structure))
    #
    #     from pprint import pprint
    #     pprint(flow_chart)


class DUCTUrbanGeometriesTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()
        self._keystore = Keystore.create(self._wd_path, 'name', 'email', 'password')
        p2p_address = PortMaster.generate_p2p_address()
        rest_address = PortMaster.generate_rest_address()
        self._node = Node.create(self._keystore, self._wd_path, p2p_address, p2p_address, rest_address)
        self._context = connect(rest_address, self._keystore)

        # create a fake project
        owner = 'owner'
        bounding_box = BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921)
        meta = ProjectMeta(
            id='prj_id',
            name='name of project',
            state='initialised',
            bounding_box=bounding_box
        )
        bdp = BaseDataPackage(
            name='bdp',
            city_name='city',
            bounding_box=bounding_box,
            grid_dimension=Dimensions(width=210, height=129),
            timezone='Asia/Singapore',
            references={}
        )
        info = ProjectInfo(
            meta=meta,
            users=[owner],
            owner=owner,
            folder=self._wd_path,
            bdp=bdp,
            bld_footprints_by_hash={},
            datasets={}
        )
        self._project = Project(None, info)
        self._project.initialise(self._context)

        # need zones for this to work
        zone_input_path = os.path.join(nextcloud_path, 'bdp_files', 'bdp-duct', 'city-admin-zones.processed')
        with open(zone_input_path, 'r') as f:
            content = json.load(f)
            features = content['features']

        group_id = self._project.geo_db.add_temporary_geometries(features)
        self._project.geo_db.import_geometries_as_zones(group_id)

    def tearDown(self):
        self._node.shutdown()
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_verify(self):
        dot = UrbanGeometries()

        result = dot.verify_content(os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_shp.zip'))
        print(result.dict())
        assert '49' in result.messages[0].message
        assert 'tree:3' in result.messages[1].message
        assert '1' in result.messages[2].message

        result = dot.verify_content(os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_geojson.zip'))
        print(result.dict())
        assert '49' in result.messages[0].message
        assert 'tree:3' in result.messages[1].message
        assert '1' in result.messages[2].message

        result = dot.verify_content(os.path.join(nextcloud_path, 'duct_dots', 'Sengkang_1003.dxf'))
        print(result.dict())
        assert len(result.messages) == 1
        assert '165' in result.messages[0].message
        for expected in ['02:tree', '01:building', '03:landuse']:
            assert expected in result.messages[0].message

        result = dot.verify_content(os.path.join(nextcloud_path, 'duct_dots', 'relocatedpark.dxf'))
        print(result.dict())
        assert len(result.messages) == 4
        assert '1' in result.messages[0].message
        assert '3' in result.messages[1].message
        assert '3' in result.messages[2].message
        assert '104' in result.messages[3].message
        for expected in ['building:5', 'relocatedpark:3414']:
            assert expected in result.messages[3].message

    def test_upload_postprocess(self):
        dot = UrbanGeometries()

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_shp.zip')
        input_path1 = os.path.join(self._wd_path, 'uploaded.zip')
        shutil.copy(input_path0, input_path1)

        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        print(result)
        assert len(result) == 3
        assert result[0][2].geo_type == GeometryType.building.value
        assert result[1][2].geo_type == GeometryType.vegetation.value
        assert result[2][2].geo_type == GeometryType.landcover.value

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_geojson.zip')
        input_path1 = os.path.join(self._wd_path, 'uploaded.zip')
        shutil.copy(input_path0, input_path1)

        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        print(result)
        assert len(result) == 3
        assert result[0][2].geo_type == GeometryType.building.value
        assert result[1][2].geo_type == GeometryType.vegetation.value
        assert result[2][2].geo_type == GeometryType.landcover.value

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'relocatedpark.dxf')
        input_path1 = os.path.join(self._wd_path, 'uploaded.dxf')
        shutil.copy(input_path0, input_path1)

        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        print(result)
        assert len(result) == 2
        assert result[0][2].geo_type == GeometryType.vegetation.value
        assert result[1][2].geo_type == GeometryType.landcover.value

    def test_update_preimport(self):
        dot = UrbanGeometries()

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_geojson', 'building.geojson')
        input_path1 = os.path.join(self._wd_path, 'uploaded')
        shutil.copy(input_path0, input_path1)

        # postprocess 'uploaded' data
        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        assert result[0][2].geo_type == GeometryType.building.value

        # the client would be using the geometries endpoint to get the GeoJSON features. we simply read the
        # building features directly from the file.
        obj_path = result[0][1]
        with open(obj_path, 'r') as f:
            content = json.load(f)
            buildings = content['features']
        assert(len(buildings) == 1)

        # we need to do some fixing -> set building height and type
        # do some fixing
        editor_config = result[0][2].editor_config
        building_height = 99
        building_type = editor_config['fields'][0]['domain']['codedValues'][0]['code']
        for building in buildings:
            # buildings should need fixing
            properties = building['properties']
            properties['height'] = building_height
            properties['building_type'] = building_type

        # fix the attributes
        result: UploadPostprocessResult = dot.update_preimport(self._project, result[0][1], {
            'features': buildings
        }, GeometryType.building)
        assert result.geo_type == GeometryType.building.value

        # check if the building has been updated
        with open(obj_path, 'r') as f:
            content = json.load(f)
            buildings = content['features']
            assert(len(buildings) == 1)

            building = buildings[0]
            assert(building['properties']['height'] == building_height)
            assert(building['properties']['building_type'] == building_type)

    def test_upload_update_import(self):
        dot = UrbanGeometries()

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'urban_geometries_shp.zip')
        input_path1 = os.path.join(self._wd_path, 'uploaded.zip')
        shutil.copy(input_path0, input_path1)

        # upload
        is_verified, verification_messages, datasets = self._project.upload_dataset(input_path1, dot)
        assert is_verified
        assert len(datasets) == 3
        bld_obj_id = datasets[0][0]
        veg_obj_id = datasets[1][0]
        lc_obj_id = datasets[2][0]
        editor_config = datasets[0][2].editor_config

        geometries = self._project.geometries(GeometryType.building, f"temp:{bld_obj_id}")
        geometries = geometries.content()
        assert geometries is not None
        buildings = geometries['features']
        assert (len(buildings) == 1)

        # we need to do some fixing -> set building height and type
        # do some fixing
        building_height = 99
        building_type = editor_config['fields'][0]['domain']['codedValues'][0]['code']
        for building in buildings:
            # buildings should need fixing
            properties = building['properties']
            properties['height'] = building_height
            properties['building_type'] = building_type

        # update
        result: UploadPostprocessResult = self._project.update_dataset(bld_obj_id, {
            'features': buildings
        }, GeometryType.building)
        assert result is not None

        # import as zone configuration
        zone_id = 317
        selected_zones = [zone_id]
        result: Dict[int, ZoneConfiguration] = \
            self._project.add_zone_configs('alt config', selected_zones=selected_zones, datasets={
                GeometryType.building: bld_obj_id,
                GeometryType.vegetation: veg_obj_id,
                GeometryType.landcover: lc_obj_id
            })
        assert(len(result) == 1)
        assert(zone_id in result)
        assert(len(result[zone_id].landcover_ids) == 80)
        assert(len(result[zone_id].vegetation_ids) == 49)
        assert(len(result[zone_id].building_ids) == 1)

        # we initialised the project from scratch. no default configurations have been created. this means there
        # should be exactly one configuration with config_id == 1
        configs = self._project.get_zone_configs(zone_id)
        assert(len(configs) == 1)
        assert(configs[0].config_id == 1)

        # we need to have another config because the Explorer assumes that by default there is at least one config
        # for each zone. if 'zone_config' is specified as prefix, it only looks into zones that have alternative
        # configs, which means a config count of >1.
        _, _, datasets = self._project.upload_dataset(input_path1, dot)
        bld_obj_id = datasets[0][0]
        veg_obj_id = datasets[1][0]
        lc_obj_id = datasets[2][0]
        geometries = self._project.geometries(GeometryType.building, f"temp:{bld_obj_id}").content()
        buildings = geometries['features']
        buildings[0]['properties']['height'] = building_height
        buildings[0]['properties']['building_type'] = building_type
        self._project.update_dataset(bld_obj_id, {'features': buildings}, GeometryType.building)
        self._project.add_zone_configs('alt config', selected_zones=selected_zones, datasets={
            GeometryType.landcover: lc_obj_id,
            GeometryType.vegetation: veg_obj_id,
            GeometryType.building: bld_obj_id
        })

        # we should have now 2 configurations
        configs = self._project.get_zone_configs(zone_id)
        assert(len(configs) == 2)

        # fetch the geometries
        lc_geometries = self._project.geometries(GeometryType.landcover, set_id=f"zone_config:{zone_id}=1").content()
        veg_geometries = self._project.geometries(GeometryType.vegetation, set_id=f"zone_config:{zone_id}=1").content()
        bld_geometries = self._project.geometries(GeometryType.building, set_id=f"zone_config:{zone_id}=1").content()
        assert(len(lc_geometries['features']) == 80)
        assert(len(veg_geometries['features']) == 49)
        assert(len(bld_geometries['features']) == 1)

        assert bld_geometries['features'][0]['properties']['height'] == building_height
        assert bld_geometries['features'][0]['properties']['building_type'] == building_type

    def test_problematic_geometries(self):
        feature0 = {
            "type": "Feature",
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [
                        [
                            [
                                103.88401528425251,
                                1.3995551509337811,
                                0.0
                            ],
                            [
                                103.8840141447084,
                                1.3995617799784765,
                                0.0
                            ],
                            [
                                103.88400904470862,
                                1.3995797799785343,
                                0.0
                            ],
                            [
                                103.88400658101324,
                                1.3995859373028816,
                                0.0
                            ],
                            [
                                103.88399788101339,
                                1.3996024373029792,
                                0.0
                            ],
                            [
                                103.8839941276229,
                                1.3996080233783317,
                                0.0
                            ],
                            [
                                103.88398212762293,
                                1.3996223233784508,
                                0.0
                            ],
                            [
                                103.88399246733371,
                                1.3996100018896505,
                                0.0
                            ],
                            [
                                103.88428163620439,
                                1.3998889925937463,
                                0.0
                            ],
                            [
                                103.88429097568793,
                                1.3998867194919187,
                                0.0
                            ],
                            [
                                103.88429396289165,
                                1.3998862556302007,
                                0.0
                            ],
                            [
                                103.88431556289147,
                                1.3998847556302179,
                                0.0
                            ],
                            [
                                103.88431659937541,
                                1.3998847138531334,
                                0.0
                            ],
                            [
                                103.88433936023355,
                                1.3998844581133105,
                                0.0
                            ],
                            [
                                103.884338827479,
                                1.399899444689451,
                                0.0
                            ],
                            [
                                103.88434107042009,
                                1.399836349953152,
                                0.0
                            ],
                            [
                                103.88434298823537,
                                1.39978326135911,
                                0.0
                            ],
                            [
                                103.88428243059114,
                                1.3996564003873262,
                                0.0
                            ],
                            [
                                103.88422788487965,
                                1.3996039283139694,
                                0.0
                            ],
                            [
                                103.88416581043305,
                                1.3995608736290144,
                                0.0
                            ],
                            [
                                103.88412629440438,
                                1.3995396098075497,
                                0.0
                            ],
                            [
                                103.88408134792309,
                                1.3995240644080453,
                                0.0
                            ],
                            [
                                103.88401591884399,
                                1.3995279306722925,
                                0.0
                            ],
                            [
                                103.88401619169981,
                                1.3995297334693535,
                                0.0
                            ],
                            [
                                103.88401648425227,
                                1.3995365509337738,
                                0.0
                            ],
                            [
                                103.88401528425251,
                                1.3995551509337811,
                                0.0
                            ]
                        ]
                    ]
                ]
            },
            "properties": {
                "landcover_type": None,
                "id": "102",
                "__attr_need_fixing": [
                    "landcover_type"
                ]
            }
        }

        feature1 = UrbanGeometries.check_feature_geometry(feature0)
        print(feature0['geometry'])
        print(feature1['geometry'])
        assert(feature0['properties'] == feature1['properties'])
        assert(feature0['geometry'] != feature1['geometry'])

        feature2 = UrbanGeometries.check_feature_geometry(feature1)
        print(feature1['geometry'])
        print(feature2['geometry'])
        assert(feature1['properties'] == feature2['properties'])
        assert(feature1['geometry'] == feature2['geometry'])


class DUCTLCZMapTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

        # create a fake project
        owner = 'owner'
        bounding_box = BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921)
        meta = ProjectMeta(
            id='prj_id',
            name='name of project',
            state='initialised',
            bounding_box=bounding_box
        )
        bdp = BaseDataPackage(
            name='bdp',
            city_name='city',
            bounding_box=bounding_box,
            grid_dimension=Dimensions(width=210, height=129),
            timezone='Asia/Singapore',
            references={}
        )
        info = ProjectInfo(
            meta=meta,
            users=[owner],
            owner=owner,
            folder=self._wd_path,
            bdp=bdp,
            bld_footprints_by_hash={},
            datasets={}
        )
        self._project = Project(None, info)

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_verify(self):
        dot = LocalClimateZoneMap()

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map0.tiff')
        result = dot.verify_content(input_path0)
        assert result.is_verified
        assert len(result.messages) == 0

        input_path1 = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map_vivek.tiff')
        result = dot.verify_content(input_path1)
        assert result.is_verified
        assert len(result.messages) == 0

    def test_upload_postprocess(self):
        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map0.tiff')
        input_path1 = os.path.join(self._wd_path, 'uploaded.tiff')
        shutil.copy(input_path0, input_path1)
        dot = LocalClimateZoneMap()

        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        print(result)
        assert len(result) == 1
        assert result[0][2].mode == 'skip'

    def test_update_preimport(self):
        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map0.tiff')
        input_path1 = os.path.join(self._wd_path, 'uploaded.tiff')
        shutil.copy(input_path0, input_path1)
        dot = LocalClimateZoneMap()

        # postprocess 'uploaded' data
        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)

        result: UploadPostprocessResult = dot.update_preimport(self._project, result[0][1], {}, None)
        assert result.mode == 'skip'

    def test_upload_update_import(self):
        # create node
        keystore = Keystore.create(self._wd_path, 'name', 'email', 'password')
        p2p_address = PortMaster.generate_p2p_address()
        rest_address = PortMaster.generate_rest_address()
        node = Node.create(keystore, self._wd_path, p2p_address, p2p_address, rest_address,
                           enable_dor=True, enable_rti=False)

        # create sdk
        sdk = connect(rest_address, keystore)

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'lcz-map0.tiff')
        input_path1 = os.path.join(self._wd_path, 'uploaded.tiff')
        shutil.copy(input_path0, input_path1)
        dot = LocalClimateZoneMap()

        # upload
        is_verified, verification_messages, datasets = self._project.upload_dataset(input_path1, dot)
        assert is_verified
        assert len(datasets) == 1

        obj_id = datasets[0][0]

        result: List[dict] = self._project.get_dataset(obj_id, sdk)
        assert result is not None
        assert len(result) == 1

        dataset = self._project.import_dataset(obj_id, sdk, 'My LCZ dataset')
        assert dataset is not None

        node.shutdown(leave_network=False)


class DUCTNSCVarTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_extract_data(self):
        input_path0 = os.path.join(nextcloud_path, 'ucmwrf_sim', 'output', 'd04-near-surface-climate')

        parameters = {
            'key': '2m_air_temperature',
            'datetime_0h': '20160417000000',
            'time': 3,
            'no_data': 999
        }
        bbox, dims, raster = extract_nsc_data(input_path0, parameters)

    def test_extract_feature_linechart(self):
        input_path0 = os.path.join(nextcloud_path, 'ucmwrf_sim', 'output', 'd04-near-surface-climate')

        parameters = {
            'legend_title': 'Air Temperature',
            'key': '2m_air_temperature',
            'datetime_0h': '20160417000000',
            'no_data': 999
        }

        dot = NearSurfaceClimateVariableLinechart()
        result = dot.extract_feature(input_path0, parameters)
        print(result)


class DUCTAHProfileTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

        # create a fake project
        owner = 'owner'
        bounding_box = BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921)
        meta = ProjectMeta(
            id='prj_id',
            name='name of project',
            state='initialised',
            bounding_box=bounding_box
        )
        bdp = BaseDataPackage(
            name='bdp',
            city_name='city',
            bounding_box=bounding_box,
            grid_dimension=Dimensions(width=210, height=129),
            timezone='Asia/Singapore',
            references={}
        )
        info = ProjectInfo(
            meta=meta,
            users=[owner],
            owner=owner,
            folder=self._wd_path,
            bdp=bdp,
            bld_footprints_by_hash={},
            datasets={}
        )
        self._project = Project(None, info)

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_csv_verify(self):
        dot = AnthropogenicHeatProfile()

        input_path0 = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_SH_20160201.csv')
        result = dot.verify_content(input_path0)
        assert result.is_verified
        assert len(result.messages) == 0

    def test_geojson_verify(self):
        dot = AnthropogenicHeatProfile()

        input_path0 = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_SH_20160201.geojson')
        result = dot.verify_content(input_path0)
        assert result.is_verified
        assert len(result.messages) == 0

    def test_geojson_upload_postprocess(self):
        input_path0 = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_SH_20160201.geojson')
        input_path1 = os.path.join(self._wd_path, 'uploaded.geojson')
        shutil.copy(input_path0, input_path1)

        dot = AnthropogenicHeatProfile()

        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        print(result)
        assert len(result) == 1
        assert result[0][2].mode == 'fix-attr-and-skip'

    def test_geojson_update_preimport(self):
        input_path0 = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_SH_20160201.geojson')
        input_path1 = os.path.join(self._wd_path, 'uploaded.geojson')
        shutil.copy(input_path0, input_path1)

        dot = AnthropogenicHeatProfile()

        # postprocess 'uploaded' data
        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)

        result: UploadPostprocessResult = dot.update_preimport(self._project, result[0][1], {}, None)
        assert result.mode == 'skip'

    def test_geojson_upload_update_import(self):
        # create node
        keystore = Keystore.create(self._wd_path, 'name', 'email', 'password')
        p2p_address = PortMaster.generate_p2p_address()
        rest_address = PortMaster.generate_rest_address()
        node = Node.create(keystore, self._wd_path, p2p_address, p2p_address, rest_address,
                           enable_dor=True, enable_rti=False)

        # create sdk
        sdk = connect(rest_address, keystore)

        input_path0 = os.path.join(nextcloud_path, 'ah_vf_mixer', 'power_baseline_SH_20160201.geojson')
        input_path1 = os.path.join(self._wd_path, 'uploaded.geojson')
        shutil.copy(input_path0, input_path1)

        dot = AnthropogenicHeatProfile()

        # upload
        is_verified, verification_messages, datasets = self._project.upload_dataset(input_path1, dot)
        assert is_verified
        assert len(datasets) == 1

        obj_id = datasets[0][0]

        result: List[dict] = self._project.get_dataset(obj_id, sdk)
        assert result is not None
        assert len(result) == 1

        dataset = self._project.import_dataset(obj_id, sdk, 'My AH dataset')
        assert dataset is not None

        node.shutdown(leave_network=False)


class DUCTBldEffStdTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

        # create a fake project
        owner = 'owner'
        bounding_box = BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921)
        meta = ProjectMeta(
            id='prj_id',
            name='name of project',
            state='initialised',
            bounding_box=bounding_box
        )
        bdp = BaseDataPackage(
            name='bdp',
            city_name='city',
            bounding_box=bounding_box,
            grid_dimension=Dimensions(width=210, height=129),
            timezone='Asia/Singapore',
            references={}
        )
        info = ProjectInfo(
            meta=meta,
            users=[owner],
            owner=owner,
            folder=self._wd_path,
            bdp=bdp,
            bld_footprints_by_hash={},
            datasets={}
        )
        self._project = Project(None, info)

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_verify(self):
        dot = BuildingEfficiencyStandard()

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'RES_CONDO_GREEN.csv')
        result = dot.verify_content(input_path0)
        assert result.is_verified
        assert len(result.messages) == 0

    def test_upload_import(self):
        # create node
        keystore = Keystore.create(self._wd_path, 'name', 'email', 'password')
        p2p_address = PortMaster.generate_p2p_address()
        rest_address = PortMaster.generate_rest_address()
        node = Node.create(keystore, self._wd_path, p2p_address, p2p_address, rest_address,
                           enable_dor=True, enable_rti=False)

        # create sdk
        sdk = connect(rest_address, keystore)

        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'RES_CONDO_GREEN.csv')
        input_path1 = os.path.join(self._wd_path, 'RES_CONDO_GREEN.csv')
        shutil.copy(input_path0, input_path1)
        dot = BuildingEfficiencyStandard()

        # upload
        is_verified, verification_messages, datasets = self._project.upload_dataset(input_path1, dot)
        assert is_verified
        assert len(datasets) == 1

        obj_id = datasets[0][0]

        result: List[dict] = self._project.get_dataset(obj_id, sdk)
        assert result is not None
        assert len(result) == 1

        dataset = self._project.import_dataset(obj_id, sdk, 'My BldEffStd dataset')
        assert dataset is not None

        # test the specification of the analysis
        analysis = BuildingEnergyEfficiency()
        spec = analysis.specification(self._project, sdk)
        eff_standards = spec.parameters_schema['properties']['efficiency_standards']['properties']
        residential_stds = eff_standards['residential']
        assert len(residential_stds['enum']) == 3
        assert len(residential_stds['enumNames']) == 3

        node.shutdown(leave_network=False)


class DUCTBuildingAHEmissionsTestCase(unittest.TestCase):
    def setUp(self):
        self._wd_path = create_wd()

    def tearDown(self):
        shutil.rmtree(self._wd_path, ignore_errors=True)

    def test_bee_aggregate_ah_data(self):
        input_path0 = os.path.join(nextcloud_path, 'bemcea_sim', 'output', 'ah_emissions')
        result = aggregate_ah_data(input_path0)
        assert result is not None

    def test_dc_aggregate_ah_data(self):
        input_path0 = os.path.join(nextcloud_path, 'dcncea_sim', 'output', 'ah_emissions')
        result = aggregate_ah_data(input_path0)
        assert result is not None


class DUCTBuildingAnnualEnergyTestCase(unittest.TestCase):
    @staticmethod
    def test_extract_feature_energy_consumption():
        bf_path = os.path.join(nextcloud_path, 'bemcea_sim', 'ZHoa2IMv', 'building.geojson')
        content_path = os.path.join(nextcloud_path, 'bemcea_sim', 'ZHoa2IMv', 'job', 'annual_energy_demand')

        with open(bf_path, 'r') as f:
            building_footprints = json.load(f)

        parameters = {
            'variable': 'energy_consumption',
            'building_footprints': building_footprints
        }

        dot = BuildingAnnualEnergy()
        result = dot.extract_feature(content_path, parameters)
        assert len(result) == 2

    @staticmethod
    def test_extract_feature_energy_use_intensity():
        bf_path = os.path.join(nextcloud_path, 'bemcea_sim', 'ZHoa2IMv', 'building.geojson')
        content_path = os.path.join(nextcloud_path, 'bemcea_sim', 'ZHoa2IMv', 'job', 'annual_energy_demand')

        with open(bf_path, 'r') as f:
            building_footprints = json.load(f)

        parameters = {
            'variable': 'energy_use_intensity',
            'building_footprints': building_footprints
        }

        dot = BuildingAnnualEnergy()
        result = dot.extract_feature(content_path, parameters)
        assert len(result) == 2

    @staticmethod
    def test_extract_feature_energy_efficiency_index():
        bf_path = os.path.join(nextcloud_path, 'bemcea_sim', 'ZHoa2IMv', 'building.geojson')
        content_path = os.path.join(nextcloud_path, 'bemcea_sim', 'ZHoa2IMv', 'job', 'annual_energy_demand')

        with open(bf_path, 'r') as f:
            building_footprints = json.load(f)

        parameters = {
            'variable': 'energy_efficiency_index',
            'building_footprints': building_footprints
        }

        dot = BuildingAnnualEnergy()
        result = dot.extract_feature(content_path, parameters)
        assert len(result) == 2


class DUCTBuildingAnnualGenerationTestCase(unittest.TestCase):
    @staticmethod
    def test_extract_feature_energy_generation():
        bf_path = os.path.join(nextcloud_path, 'bemcea_sim', '6fvbEVCy', 'building.geojson')
        content_path = os.path.join(nextcloud_path, 'bemcea_sim', '6fvbEVCy', 'job', 'pv_potential')

        with open(bf_path, 'r') as f:
            building_footprints = json.load(f)

        parameters = {
            'variable': 'energy_generation',
            'building_footprints': building_footprints
        }

        dot = BuildingAnnualGeneration()
        result = dot.extract_feature(content_path, parameters)
        assert len(result) == 2


class DUCTSupplySystemsTestCase(unittest.TestCase):
    @staticmethod
    def test_create_system_summary_charts():
        supply_systems_path = os.path.join(nextcloud_path, 'dcncea_sim', 'output', 'supply_systems')
        with open(supply_systems_path, 'r') as f:
            content = json.load(f)

        result = create_system_summary_charts(content['DCS'], 'DCS_101')
        print(result)
        assert len(result) == 3

    @staticmethod
    def test_create_network_map():
        supply_systems_path = os.path.join(nextcloud_path, 'dcncea_sim', 'output', 'supply_systems')
        with open(supply_systems_path, 'r') as f:
            content = json.load(f)

        dcs_name = 'DCS_101'
        cluster_name = 'N1005'
        result = create_network_map(content['DCS'][dcs_name][cluster_name]['network'], dcs_name, cluster_name)
        print(result)

    @staticmethod
    def test_create_connected_building_map():
        supply_systems_path = os.path.join(nextcloud_path, 'dcncea_sim', 'output', 'supply_systems')
        with open(supply_systems_path, 'r') as f:
            content = json.load(f)

        building_footprints_path = os.path.join(nextcloud_path, 'dcncea_sim', 'input', 'building.geojson')
        with open(building_footprints_path, 'r') as f:
            building_footprints = json.load(f)

        dcs_name = 'DCS_101'
        cluster_name = 'N1005'
        network_map = create_network_map(content['DCS'][dcs_name][cluster_name]['network'], dcs_name, cluster_name)
        result = create_connected_building_map(network_map, building_footprints)
        print(result)

    @staticmethod
    def test_create_pie_charts():
        supply_systems_path = os.path.join(nextcloud_path, 'dcncea_sim', 'output', 'supply_systems')
        with open(supply_systems_path, 'r') as f:
            content = json.load(f)

        dcs_name = 'DCS_101'
        cluster_name = 'N1005'
        result = create_pie_charts(content['DCS'][dcs_name][cluster_name]['structure'])
        print(result)

    @staticmethod
    def test_create_network_flow_chart():
        supply_systems_path = os.path.join(nextcloud_path, 'dcncea_sim', 'output', 'supply_systems')
        with open(supply_systems_path, 'r') as f:
            content = json.load(f)

        dcs_name = 'DCS_101'
        cluster_name = 'N1005'
        result = create_network_flow_chart(content['DCS'][dcs_name][cluster_name]['structure'])
        print(result)


if __name__ == '__main__':
    unittest.main()
