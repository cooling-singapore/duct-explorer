from explorer.renderer.base import GeometriesRenderer


class BuildingsRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            'type': 'unique-value',
            'field': 'building_type',
            'defaultSymbol': {
                'type': 'polygon-3d',
                'symbolLayers': [
                    {
                        'type': 'extrude',
                        'size': 1,
                        'material': {
                            'color': [255, 255, 255, 1]
                        },
                        'edges': {
                            'type': 'solid',
                            'color': [1, 1, 1],
                            'size': 0.5,
                        }
                    }
                ],
            },
            'defaultLabel': 'Other',
            'uniqueValueGroups': [
                {
                    'classes': [
                        {
                            'label': 'Residential',
                            'symbol': {
                                'type': 'polygon-3d',
                                'symbolLayers': [
                                    {
                                        'type': 'extrude',
                                        'size': 1,
                                        'material': {
                                            'color': [250, 213, 149, 1]
                                        },
                                        'edges': {
                                            'type': 'solid',
                                            'color': [1, 1, 1],
                                            'size': 0.5
                                        }
                                    }
                                ]
                            },
                            'values': ['residential:1', 'residential:2']
                        }
                    ]
                },
                {
                    'classes': [
                        {
                            'label': 'Commercial',
                            'symbol': {
                                'type': 'polygon-3d',
                                'symbolLayers': [
                                    {
                                        'type': 'extrude',
                                        'size': 1,
                                        'material': {
                                            'color': [156, 183, 221, 1]
                                        },
                                        'edges': {
                                            'type': 'solid',
                                            'color': [1, 1, 1],
                                            'size': 0.5
                                        }
                                    }
                                ]
                            },
                            'values': [
                                'commercial:2',
                                'commercial:3',
                                'commercial:4',
                                'commercial:5',
                                'commercial:6',
                                'commercial:7',
                                'commercial:8',
                                'commercial:9',
                                'commercial:10'
                            ]
                        }
                    ]
                },
                {
                    'classes': [
                        {
                            'label': 'Office',
                            'symbol': {
                                'type': 'polygon-3d',
                                'symbolLayers': [
                                    {
                                        'type': 'extrude',
                                        'size': 1,
                                        'material': {
                                            'color': [236, 162, 171, 1]
                                        },
                                        'edges': {
                                            'type': 'solid',
                                            'color': [1, 1, 1],
                                            'size': 0.5
                                        }
                                    }
                                ]
                            },
                            'values': 'commercial:1'
                        }
                    ]
                },
                {
                    'classes': [
                        {
                            'label': 'Industrial',
                            'symbol': {
                                'type': 'polygon-3d',
                                'symbolLayers': [
                                    {
                                        'type': 'extrude',
                                        'size': 1,
                                        'material': {
                                            'color': [190, 169, 209, 1]
                                        },
                                        'edges': {
                                            'type': 'solid',
                                            'color': [1, 1, 1],
                                            'size': 0.5
                                        }
                                    }
                                ]
                            },
                            'values': ['industrial:1', 'industrial:2', 'industrial:3']
                        }
                    ]
                },
                {
                    'classes': [
                        {
                            'label': 'Passive',
                            'symbol': {
                                'type': 'polygon-3d',
                                'symbolLayers': [
                                    {
                                        'type': 'extrude',
                                        'size': 1,
                                        'material': {
                                            'color': [164, 224, 177, 1]
                                        },
                                        'edges': {
                                            'type': 'solid',
                                            'color': [1, 1, 1],
                                            'size': 0.5
                                        }
                                    }
                                ]
                            },
                            'values': ['commercial:11', 'commercial:12']
                        }
                    ]
                }
            ],
            'visualVariables': [
                {
                    'type': 'size',
                    'field': 'height',
                    'valueUnit': 'meters',
                    'legendOptions': {
                        'showLegend': False
                    }
                }
            ]
        }


class BuildingConnectRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            'type': 'unique-value',
            'field': 'connected',
            'uniqueValueInfos': [
                {
                    'value': 'connected',
                    'symbol': {
                        'type': 'polygon-3d',
                        'symbolLayers': [
                            {
                                'type': 'extrude',
                                'size': 1,
                                'material': {
                                    'color': [156, 183, 221, 1]
                                },
                                'edges': {
                                    'type': 'solid',
                                    'color': [1, 1, 1],
                                    'size': 0.5
                                }
                            }
                        ]
                    },
                    'label': 'Connected buildings',
                },
                {
                    'value': 'not_connected',
                    'symbol': {
                        'type': 'polygon-3d',
                        'symbolLayers': [
                            {
                                'type': 'extrude',
                                'size': 1,
                                'material': {
                                    'color': [255, 255, 255, 1]
                                },
                                'edges': {
                                    'type': 'solid',
                                    'color': [1, 1, 1],
                                    'size': 0.5
                                }
                            }
                        ]
                    },
                    'label': 'Non-connected buildings',
                }
            ],
            'label': 'Selected buildings',
            'visualVariables': [
                {
                    'type': 'size',
                    'field': 'height',
                    'valueUnit': 'meters',
                    'legendOptions': {
                        'showLegend': False,
                    }
                }
            ]
        }

