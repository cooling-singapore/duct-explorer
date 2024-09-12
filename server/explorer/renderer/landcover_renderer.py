from explorer.renderer.base import GeometriesRenderer


class LandcoverRenderer(GeometriesRenderer):
    def get(self) -> dict:
        return {
            "type": "unique-value",
            "field": "landcover_type",
            "defaultLabel": "Unknown",
            "defaultSymbol": {
                "type": "simple-fill",
                "color": [255, 0, 0, 0.9],
                "style": "diagonal-cross",
                "outline": {"color": [255, 0, 0, 0.9], "width": "3"}
            },
            "uniqueValueGroups": [
                {
                    "heading": "Soil",
                    "classes": [
                        {
                            "label": "Coarse / Medium / Medium-fine / Fine / Very fine / Organic",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [99, 69, 32, 0.9],
                                "style": "solid"
                            },
                            "values": [
                                "soil:1",
                                "soil:2",
                                "soil:3",
                                "soil:4",
                                "soil:5",
                                "soil:6"
                            ]
                        }
                    ]
                },
                {
                    "heading": "Vegetation",
                    "classes": [
                        {
                            "label": "Bare soil",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [99, 69, 32, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:1"
                        },
                        {
                            "label": "Crops, mixed farming / Irrigated crops",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [209, 171, 78, 0.9],
                                "style": "solid"
                            },
                            "values": ["vegetation:2", "vegetation:11"]
                        },
                        {
                            "label": " Short grass / Tall grass",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [189, 219, 124, 0.9],
                                "style": "solid"
                            },
                            "values": ["vegetation:3", "vegetation:8"]
                        },
                        {
                            "label": "Evergreen shrubs / Deciduous shrubs",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [101, 130, 41, 0.9],
                                "style": "solid"
                            },
                            "values": ["vegetation:15", "vegetation:16"]
                        },
                        {
                            "label": "Evergreen broadleaf trees",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [44, 67, 38, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:6"
                        },
                        {
                            "label": "Deciduous broadleaf trees",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [90, 197, 58, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:7"
                        },
                        {
                            "label": "Evergreen needleleaf trees",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [28, 72, 15, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:4"
                        },
                        {
                            "label": "Deciduous needleleaf trees",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [70, 156, 44, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:5"
                        },
                        {
                            "label": "Mixed forest/woodland / Interrupted forest",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [82, 180, 74, 0.9],
                                "style": "solid"
                            },
                            "values": ["vegetation:17", "vegetation:18"]
                        },
                        {
                            "label": "Bogs and marshes",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [16, 1, 77, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:14"
                        },
                        {
                            "label": "Tundra",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [164, 192, 153, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:10"
                        },
                        {
                            "label": "Desert / Semi desert",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [238, 129, 59, 0.9],
                                "style": "solid"
                            },
                            "values": ["vegetation:9", "vegetation:12"]
                        },
                        {
                            "label": "Ice caps and glaciers",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [232, 230, 250, 0.9],
                                "style": "solid"
                            },
                            "values": "vegetation:13"
                        }
                    ]
                },
                {
                    "heading": "Pavement",
                    "classes": [
                        {
                            "label": "Asphalt/concrete mix",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [89, 84, 88, 0.9],
                                "style": "solid"
                            },
                            "values": "pavement:1"
                        },
                        {
                            "label": "Asphalt",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [128, 128, 128, 0.9],
                                "style": "solid"
                            },
                            "values": "pavement:2"
                        },
                        {
                            "label": "Concrete",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [166, 166, 166, 0.9],
                                "style": "solid"
                            },
                            "values": "pavement:3"
                        },
                        {
                            "label": "Gravel / Fine gravel",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [230, 230, 230, 0.9],
                                "style": "solid"
                            },
                            "values": ["pavement:9", "pavement:10"]
                        },
                        {
                            "label": "Metal",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [202, 211, 215, 0.9],
                                "style": "solid"
                            },
                            "values": "pavement:7"
                        },
                        {
                            "label": "Sett / Pebblestone / Paving stones / Cobblestone",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [240, 153, 92, 0.9],
                                "style": "solid"
                            },
                            "values": ["pavement:4", "pavement:5", "pavement:6", "pavement:11"]
                        },
                        {
                            "label": "Wood / Woodchips",
                            "symbol": {
                                "type": "simple-fill",
                                "color": [123, 81, 36, 0.9],
                                "style": "solid"
                            },
                            "values": ["pavement:8", "pavement:12"]
                        }
                    ]
                },
                {
                    "heading": "Water",
                    "classes": [
                        {
                            "label": "Lake / River / Ocean / Pond / Fountain",
                            "symbol": {
                                "type": "polygon-3d",
                                "symbolLayers": [
                                    {
                                        "type": "water",
                                        "waveDirection": 180,
                                        "color": "#5975a3",
                                        "waveStrength": "moderate",
                                        "waterbodySize": "small"
                                    }
                                ]
                              },
                            "values": ["water:1", "water:2", "water:3", "water:4", "water:5"]
                        }
                    ]
                }
            ]
        }
