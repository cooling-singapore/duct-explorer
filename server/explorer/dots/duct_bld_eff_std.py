import os
from shutil import copyfile
from typing import Dict, List, Optional, Tuple

from saas.core.helpers import get_timestamp_now
from saas.core.logging import Logging

from explorer.exceptions import DUCTRuntimeError
from explorer.dots.dot import ImportableDataObjectType, UploadPostprocessResult, ImportTarget, DOTVerificationMessage, \
    DOTVerificationResult
from explorer.geodb import GeometryType
from explorer.schemas import ExplorerRuntimeError

logger = Logging.get('explorer.dots.bld_eff_std')


class BuildingEfficiencyStandard(ImportableDataObjectType):
    DATA_TYPE = 'duct.bld-eff-standard'

    @classmethod
    def read_as_csv(cls, path: str, messages: List[DOTVerificationMessage] = None) \
            -> Optional[Tuple[str, List[list[str]]]]:
        try:
            with open(path, 'r') as f:
                # read all lines
                lines = f.readlines()
                if len(lines) < 71:
                    if messages:
                        messages.append(DOTVerificationMessage(
                            severity='error', message=f"File structure appears to be invalid: "
                                                      f"found {len(lines)} lines, expected 72 lines"))

                    raise ExplorerRuntimeError(f"Unexpected number of lines: expected=72 actual={len(lines)}")

                # split the fields
                lines = [[field for field in line.strip().split(',') if field] for line in lines]

                # determine building type and name
                if lines[0][0] != 'Building Type' or len(lines[0]) != 2:
                    if messages:
                        messages.append(DOTVerificationMessage(
                            severity='error', message=f"Building Type information missing"))
                    raise ExplorerRuntimeError("Building Type information missing")
                building_type = lines[0][1]

                # is the building type valid?
                if building_type not in ['residential', 'office', 'commercial']:
                    if messages:
                        messages.append(DOTVerificationMessage(
                            severity='error', message=f"Unexpected building type '{building_type}'"))
                    raise ExplorerRuntimeError(f"Unexpected building type: {building_type}")

                return building_type, lines

        except Exception:
            return None  # at this point we assume it's not a GeoJSON

    def target(self) -> ImportTarget:
        return ImportTarget.library

    def name(self) -> str:
        return self.DATA_TYPE

    def label(self) -> str:
        return 'Building Energy Efficiency Standard'

    def supported_formats(self) -> List[str]:
        return ['csv']

    def description(self) -> str:
        return "New building efficiency standards can be defined based on an already existing building type (e.g. " \
               "Residential). You may download the template of a condensed database to modify pre-selected building"\
               " parameters and reimport them. <br><br> " \
               "<a href='./assets/importExamples/Commercial-retail.csv' download>Commercial.csv</a> <br>" \
               "<a href='./assets/importExamples/Residential-multi-res.csv' download>Residential.csv</a> <br>" \
               "<a href='./assets/importExamples/Office.csv' download>Office.csv</a> <br><br>" \
               "<b>Required data attributes:</b>" \
               "<ul><li>Building envelope parameters</li></ul>" \
               "<ul><li>Building schedule</li></ul>" \
               "<ul><li>Internal loads</li></ul>" \
               "<b>Accepted file formats:</b>" \
               "<ul><li>csv</li></ul>"

    def preview_image_url(self) -> str:
        return 'dot_bld-eff-standard.png'

    def upload_postprocess(self, project, temp_obj_path: str) -> List[Tuple[str, str, UploadPostprocessResult]]:
        from explorer.project import Project
        project: Project = project

        # we just copy the file
        obj_id = f"{self.name()}_{get_timestamp_now()}"
        obj_path = os.path.join(project.info.temp_path, obj_id)
        copyfile(temp_obj_path, obj_path)

        # obtain the building type
        building_type, _ = self.read_as_csv(obj_path)

        result = [(obj_id, obj_path, UploadPostprocessResult(title='', description='', mode='skip', extra={
            'building_type': building_type
        }))]
        return result

    def update_preimport(self, project, obj_path: str, args: dict,
                         geo_type: Optional[GeometryType]) -> UploadPostprocessResult:
        return UploadPostprocessResult(title='', description='', mode='skip', extra={})

    def verify_content(self, content_path: str) -> DOTVerificationResult:
        # try to read as CSV:
        messages = []
        content, data_format = self.read_as_csv(content_path, messages), 'csv'

        # if we don't have any content here, then we couldn't read the data
        if content is None:
            data_format = 'unknown'
            messages.append(DOTVerificationMessage(
                severity='error', message=f"Data cannot be read as CSV."
            ))

        # do we have any errors?
        is_verified = True
        for message in messages:
            if message.severity == 'error':
                is_verified = False
                break

        return DOTVerificationResult(messages=messages, is_verified=is_verified, data_format=data_format)

    def extract_feature(self, content_path: str, parameters: dict) -> Dict:
        return {}

    def extract_delta_feature(self, content_path0: str, content_path1: str, parameters: dict) -> Dict:
        raise DUCTRuntimeError(f"Not implemented")

    def export_feature(self, content_path: str, parameters: dict, export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")

    def export_delta_feature(self, content_path0: str, content_path1: str, parameters: dict,
                             export_path: str, export_format: str) -> None:
        raise DUCTRuntimeError(f"Not implemented")
