import os

from explorer.bdp.bdp import DUCTBaseDataPackageDB
from explorer.dots.duct_ahprofile import AnthropogenicHeatProfile
from explorer.dots.duct_lcz import LocalClimateZoneMap
from explorer.schemas import BoundingBox, Dimensions, BaseDataPackage


# def test_bdp_create_duct(wd_path, bdp_source_path, node_context):
#     caz_processed_path = os.path.join(bdp_source_path, 'city-admin-zones.processed')
#     luz_processed_path = os.path.join(bdp_source_path, 'land-use.processed')
#     lc_processed_path = os.path.join(bdp_source_path, 'land-cover.processed')
#     bld_processed_path = os.path.join(bdp_source_path, 'building-footprints.processed')
#     veg_processed_path = os.path.join(bdp_source_path, 'vegetation.processed')
#     need_to_prepare = not (os.path.isfile(caz_processed_path) and os.path.isfile(luz_processed_path) and
#                            os.path.isfile(bld_processed_path) and os.path.isfile(veg_processed_path) and
#                            os.path.isfile(lc_processed_path))
#
#     # prepare files
#     if need_to_prepare:
#         mapping = DUCTBaseDataPackageDB.prepare_files({
#             'city-admin-zones': {
#                 'path': os.path.join(bdp_source_path, 'city-admin-zones'),
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'land-use': {
#                 'path': os.path.join(bdp_source_path, 'land-use'),
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'building-footprints': {
#                 'path': os.path.join(bdp_source_path, 'building-footprints'),
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'vegetation': {
#                 'path': os.path.join(bdp_source_path, 'vegetation'),
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             # land-cover will be derived from land-use (as a workaround for lack of actual data)
#             'lcz-baseline': {
#                 'path': os.path.join(bdp_source_path, 'lcz-baseline'),
#                 'type': LocalClimateZoneMap.DATA_TYPE,
#                 'format': 'tiff'
#             },
#             'sh-traffic-baseline': {
#                 'path': os.path.join(bdp_source_path, 'sh-traffic-baseline'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'sh-traffic-ev100': {
#                 'path': os.path.join(bdp_source_path, 'sh-traffic-ev100'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'sh-power-baseline': {
#                 'path': os.path.join(bdp_source_path, 'sh-power-baseline'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'lh-power-baseline': {
#                 'path': os.path.join(bdp_source_path, 'lh-power-baseline'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'description': {
#                 'path': os.path.join(bdp_source_path, 'description'),
#                 'type': 'BDPDescription',
#                 'format': 'markdown'
#             }
#         })
#     else:
#         mapping = {
#             'city-admin-zones': {
#                 'path': caz_processed_path,
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'land-use': {
#                 'path': luz_processed_path,
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'building-footprints': {
#                 'path': bld_processed_path,
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'vegetation': {
#                 'path': veg_processed_path,
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'land-cover': {
#                 'path': lc_processed_path,
#                 'type': 'DUCT.GeoVectorData',
#                 'format': 'geojson'
#             },
#             'lcz-baseline': {
#                 'path': os.path.join(bdp_source_path, 'lcz-baseline'),
#                 'type': LocalClimateZoneMap.DATA_TYPE,
#                 'format': 'tiff'
#             },
#             'sh-traffic-baseline': {
#                 'path': os.path.join(bdp_source_path, 'sh-traffic-baseline'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'sh-traffic-ev100': {
#                 'path': os.path.join(bdp_source_path, 'sh-traffic-ev100'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'sh-power-baseline': {
#                 'path': os.path.join(bdp_source_path, 'sh-power-baseline'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'lh-power-baseline': {
#                 'path': os.path.join(bdp_source_path, 'lh-power-baseline'),
#                 'type': AnthropogenicHeatProfile.DATA_TYPE,
#                 'format': 'geojson'
#             },
#             'description': {
#                 'path': os.path.join(bdp_source_path, 'description'),
#                 'type': 'BDPDescription',
#                 'format': 'markdown'
#             }
#         }
#
#     # upload BDP
#     bdp = BaseDataPackage.upload(
#         node_context, 'Singapore', 'Public Dataset (test)',
#         BoundingBox(west=103.55161, north=1.53428, east=104.14966, south=1.19921),
#         Dimensions(width=211, height=130), 'Asia/Singapore', mapping
#     )
#
#     # create the BDP
#     paths = DUCTBaseDataPackageDB.create(wd_path, bdp, node_context)
#     assert paths is not None
#     assert os.path.isfile(paths[0])
#     assert os.path.isfile(paths[1])
#     assert '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4' in paths[0]
#     assert '4fc2e31f6864f856db6c24463a98b4e93954bc97d89e807d702a0343507b35d4' in paths[1]
