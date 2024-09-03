import Graphic from '@arcgis/core/Graphic';

import { useImport } from '../../context/import.context';
import { ImportStage } from '@duct-core/data';
import AreaSelectionLayer from '../../utils/ui/map-layers/area-selection-layer';
import BaseMap from '../../utils/ui/map-layers/base-map';
import TempImportLayer from '../../utils/ui/map-layers/temp-import-layer';
import ZonePickerLayer from '../../utils/ui/map-layers/zone-picker-layer';

function ImportMapLayers() {
  const importContext = useImport();
  const showZoneSelector =
    importContext.context.importStage === ImportStage.ZoneSelection;

  const uploadResponse = importContext.context.uploadResponse;

  const zoneAdded = (feature: Graphic) => {
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.selectedZones?.delete(feature.attributes['__OBJECTID']);
      return copy;
    });
  };

  const zoneRemoved = (feature: Graphic) => {
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      const zones = copy.selectedZones || new Set<number>();
      zones.add(feature.attributes['__OBJECTID']);
      //   if (copy) {
      copy.selectedZones = zones;
      //   } else {
      //     copy['importFootprint'] = { selectedZones: zones };
      //   }
      return copy;
    });
  };

  const onSketchComplete = (shape: string) => {
    importContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.areaGeoJson = shape;
      return copy;
    });
  };

  return (
    <>
      <BaseMap />
      <ZonePickerLayer
        showZonePicker={showZoneSelector}
        onZoneAdded={zoneAdded}
        onZoneRemoved={zoneRemoved}
      />

      <AreaSelectionLayer
        visible={importContext.context.showAreaSelection}
        returnGeoJson
        onAreaSelected={onSketchComplete}
      />
      {uploadResponse?.datasets.map((dataSet, index) => (
        <TempImportLayer
          key={`layer-${index}-${dataSet.obj_id}`}
          editable={
            !showZoneSelector && dataSet.info.editor_config ? true : false
          }
          visible={true}
          dataSet={dataSet}
        />
      ))}
    </>
  );
}

export default ImportMapLayers;
