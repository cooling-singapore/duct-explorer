from typing import List

from saas.core.logging import Logging
from saas.sdk.base import SDKContext

from duct.dots.duct_lcz import LocalClimateZoneMap
from explorer.module.base import BuildModule
from explorer.project import Project
from explorer.schemas import BuildModuleSpecification

logger = Logging.get('duct.modules.lulc')


class LandUseLandCoverModule(BuildModule):
    def name(self) -> str:
        return 'landuse-landcover'

    def label(self) -> str:
        return 'Local Climate Zone'

    def type(self) -> str:
        return 'meso'

    def specification(self, project: Project) -> BuildModuleSpecification:
        lcz_obj_id = [project.info.bdp.references['lcz-baseline']]
        lcz_labels = ['Default']
        for dataset in project.info.datasets.values():
            if dataset.type == LocalClimateZoneMap.DATA_TYPE:
                lcz_obj_id.append(dataset.obj_id)
                lcz_labels.append(dataset.name)

        return BuildModuleSpecification.parse_obj({
            'name': self.name(),
            'label': self.label(),
            'type': self.type(),
            'priority': 202,
            'description': 'Local Climate Zones (LCZ) are representations of urban surfaces as proposed by Stewart '
                           'and Oke. Import new LCZ maps and select the one you would like to apply in this scene. '
                           'For a detailed guide on importing LCZ maps, please click '
                           '<a href="" target="_blank">here</a>.',
            'parameters_schema': {
                'type': 'object',
                'properties': {
                    'lcz_obj_id': {
                        'type': 'string',
                        'title': 'Selected Local Climate Zone Map',
                        'enum': lcz_obj_id,
                        'enumNames': lcz_labels,
                        'default': lcz_obj_id[0]
                    }
                },
                'required': ['lcz_obj_id']
            },
            'has_raster_map': True,
            'has_update_map': False,
            'has_area_selector': False,
            'hide_settings_accordion': False,
            'editable': False,
            'editorConfig': {},
            'ui_schema': {},
            'icon': 'lulc.svg'
        })

    def raster_image(self, project: Project, parameters: dict, sdk: SDKContext) -> List[dict]:
        # update the LCZ map
        lcz_obj_id = parameters['module_settings'][self.name()]['lcz_obj_id']
        project.vf_mixer.update_lcz(lcz_obj_id, sdk)

        return [project.vf_mixer.raster_lcz()]

    def chart(self, project: Project, parameters: dict, sdk: SDKContext) -> dict:
        return {}
