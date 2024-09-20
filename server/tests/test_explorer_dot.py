import logging
import os
import shutil
import unittest

from typing import Tuple, List

from tests.base_testcase import create_wd

from saas.core.logging import Logging

from explorer.dots.area_of_interest import AreaOfInterest
from explorer.dots.dot import UploadPostprocessResult
from explorer.project import Project
from explorer.schemas import ProjectInfo, BaseDataPackage, BoundingBox, Dimensions, ProjectMeta

Logging.initialise(logging.INFO)
logger = Logging.get(__name__, level=logging.DEBUG)

nextcloud_path = os.path.join(os.environ['HOME'], 'Nextcloud', 'DT-Lab', 'Testing')


class ExplorerDOTTestCase(unittest.TestCase):
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

    def test_geojson_verify(self):
        input_path = os.path.join(nextcloud_path, 'duct_dots', 'aoi.geojson')
        dot = AreaOfInterest()

        result = dot.verify_content(input_path)
        assert result.is_verified

    def test_shp_verify(self):
        input_path = os.path.join(nextcloud_path, 'duct_dots', 'aoi.zip')
        dot = AreaOfInterest()

        result = dot.verify_content(input_path)
        assert result.is_verified

    def test_upload_postprocess(self):
        input_path0 = os.path.join(nextcloud_path, 'duct_dots', 'aoi.zip')
        input_path1 = os.path.join(self._wd_path, 'uploaded')
        shutil.copy(input_path0, input_path1)
        dot = AreaOfInterest()

        result: List[Tuple[str, str, UploadPostprocessResult]] = dot.upload_postprocess(self._project, input_path1)
        print(result)
        assert len(result) == 1


if __name__ == '__main__':
    unittest.main()
