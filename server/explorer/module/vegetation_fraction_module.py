from typing import List

from saas.core.logging import Logging

from saas.sdk.base import SDKContext

from explorer.module.base import BuildModule
from explorer.project import Project
from explorer.schemas import BuildModuleSpecification

logger = Logging.get('duct.modules.vegfrac')


def _make_marks(v_default: int, v_max: int) -> List[dict]:
    # create a list of marks including the default and max values
    marks = list(range(0, v_default, 5))

    # remove the last mark if too close to the default
    if abs(marks[-1] - v_default) < 3:
        marks = marks[:-1]

    # add the default and max values
    marks.append(v_default)
    if v_max != v_default:
        marks.append(v_max)

    # convert it into what is needed for the schema
    show = [0, v_default, v_max, 100]
    marks = [
        {'value': v, 'label': f'{v}%'} if v in show else {'value': v} for v in marks
    ]

    return marks


class VegetationFractionModule(BuildModule):
    lcz_names = [
        'Compact High-rise Areas (LCZ1)', 'Compact Mid-rise Areas (LCZ2)', 'Compact Low-rise Areas (LCZ3)',
        'Open High-rise Areas (LCZ4)', 'Open Mid-rise Areas (LCZ5)', 'Open Low-rise Areas (LCZ6)',
        'Lightweight Low-rise Areas (LCZ7)', 'Large Low-rise Areas (LCZ8)', 'Sparsely built Areas (LCZ9)',
        'Heavy Industry Areas (LCZ10)'
    ]
    vf_defaults = [100-66, 100-65, 100-65, 100-48, 100-48, 100-48, 100-90, 100-78, 100-13, 100-80]

    def name(self) -> str:
        return 'vegetation-fraction'

    def label(self) -> str:
        return 'Vegetation Fraction'

    def type(self) -> str:
        return 'meso'

    def specification(self, project: Project) -> BuildModuleSpecification:
        properties = {}
        for i in range(10):
            # create marks for this LCZ
            v_default = self.vf_defaults[i]
            v_max = self.vf_defaults[i] + 10 if i < (7 - 1) else self.vf_defaults[i]  # default is max for LCZ7-10
            marks = _make_marks(v_default, v_max)

            properties[f"p_lcz{i+1}"] = {
                'title': self.lcz_names[i],
                'type': 'integer',
                'step': None,
                'default': self.vf_defaults[i],
                'defaultValue': self.vf_defaults[i],
                'marks': marks
            }

        return BuildModuleSpecification.parse_obj({
            'name': self.name(),
            'label': self.label(),
            'type': self.type(),
            'priority': 201,
            'description': 'Modify the percentage of vegetation coverage within each designated Local Climate Zone ('
                           'LCZ). By default, the slider is set at the baseline value and can be changed up to a '
                           'specified maximum limit for each LCZ category.',
            'parameters_schema': {
                'type': 'object',
                'properties': properties,
                'required': [f'p_lcz{i+1}' for i in range(10)]
            },
            'has_raster_map': True,
            'has_update_map': False,
            'has_area_selector': False,
            'hide_settings_accordion': False,
            'editable': False,
            'editorConfig': {},
            'ui_schema': {f"p_lcz{i+1}": {"ui:widget": "rangeWidget"} for i in range(10)},
            'icon': 'vegetation.svg',
            'settings_description': 'Local Climate Zones (LCZs) according to Stewart, I.D., and T. R. Oke, 2012: '
                                    'Local Climate Zones for Urban Temperature Studies. Bull. Amer. Meteor. Soc., 93, '
                                    '1879–1900, https://doi.org/10.1175/BAMS-D-11-00019.1.',
            'settings_image': 'lcz_legend.png'
        })

    def raster_image(self, project: Project, parameters: dict, sdk: SDKContext) -> List[dict]:
        module_settings = parameters['module_settings'][self.name()]
        return [project.vf_mixer.raster_vf(module_settings)]

    def chart(self, project: Project, parameters: dict, sdk: SDKContext) -> dict:
        return {}
