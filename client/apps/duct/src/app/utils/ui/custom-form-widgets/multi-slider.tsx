import { MultiSliderProps, MultiSliderSelectItem } from '@duct-core/data';

import {
  Alert,
  Avatar,
  Box,
  Chip,
  FormControl,
  InputLabel,
  ListItemIcon,
  MenuItem,
  OutlinedInput,
  Select,
  SelectChangeEvent,
  Slider,
  Typography,
} from '@mui/material';
import { FieldProps } from '@rjsf/utils';
import { useEffect, useState } from 'react';
import { useScene } from '../../../context/scene.context';

const ITEM_HEIGHT = 48;
const ITEM_PADDING_TOP = 8;
const MenuProps = {
  PaperProps: {
    style: {
      maxHeight: ITEM_HEIGHT * 4.5 + ITEM_PADDING_TOP,
      width: 250,
    },
  },
};

interface SliderData {
  name: string;
  value: number;
}

function MultiSlider(props: FieldProps<SliderData[]>) {
  const { onChange, formData, schema: formSchema, disabled } = props;
  const schema = props.uiSchema as MultiSliderProps;
  const sceneContext = useScene();
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [formErrors, setformErrors] = useState<string[]>([]);
  const [selectedMultiSliderItems, setSelectedMultiSliderItems] = useState<
    MultiSliderSelectItem[]
  >([]);

  const buildSliderList = () => {
    const temp: MultiSliderSelectItem[] = [];
    for (const [i, value] of selectedItems.entries()) {
      const result = schema.options.find((option) => option.value === value);

      if (result) {
        temp.push(result);
      }
    }
    setSelectedMultiSliderItems(temp);
  };

  useEffect(() => {
    buildSliderList();
    // remove from formData if user removes item from multiselect
    if (formData) {
      const newFormData = formData.filter((el) =>
        selectedItems.some((f) => f === el.name)
      );
      onChange(newFormData);
    }
  }, [selectedItems]);

  const handleChange = (event: SelectChangeEvent<typeof selectedItems>) => {
    const {
      target: { value },
    } = event;
    setSelectedItems(
      // On autofill we get a stringified value.
      typeof value === 'string' ? value.split(',') : value
    );
  };

  const evaluateTotals = () => {
    if (formData) {
      // calculate total of all sliders
      const total = formData.reduce(
        (accumulator, item) => accumulator + item.value,
        0
      );

      if (total === 100) {
        setformErrors(() => []);
        sceneContext.setContext((prevState) => {
          const copy = { ...prevState };
          copy.errors.delete(schema.module_name);
          return copy;
        });
      } else {
        setformErrors(() => [
          `The total values of the sliders should be euqal to 100. The current total is ${total}`,
        ]);

        // used for scene validation
        sceneContext.setContext((prevState) => {
          const copy = { ...prevState };
          copy.errors.add(schema.module_name);
          return copy;
        });
      }
    }
  };

  return (
    <>
      {formSchema.title && (
        <Typography variant="h5" gutterBottom>
          {formSchema.title}
        </Typography>
      )}
      {formSchema.description && (
        <Typography variant="body2" sx={{ mb: 2 }}>
          {formSchema.description}
        </Typography>
      )}
      <FormControl>
        <InputLabel id="demo-multiple-chip-label">
          {schema.multi_select_label}
        </InputLabel>
        <Select
          labelId="demo-multiple-chip-label"
          id="demo-multiple-chip"
          multiple
          value={selectedItems}
          onChange={handleChange}
          input={<OutlinedInput id="select-multiple-chip" label="Chip" />}
          renderValue={(selected) => (
            <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
              {selected.map((value) => (
                <Chip key={`chip-${value}`} label={value} />
              ))}
            </Box>
          )}
          MenuProps={MenuProps}
          disabled={disabled}
        >
          {schema.options.map((option) => (
            <MenuItem key={`menu-${option.value}`} value={option.value}>
              {option.color && (
                <ListItemIcon>
                  <Avatar
                    variant="rounded"
                    sx={{ bgcolor: option.color, width: 20, height: 20 }}
                  >
                    <></>
                  </Avatar>
                </ListItemIcon>
              )}

              {option.label}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {selectedMultiSliderItems.map((item) => (
        <Box mt={2} key={item.value}>
          {item.label}
          <Slider
            color="secondary"
            min={schema.slider_config.min}
            max={schema.slider_config.max}
            step={schema.slider_config.step}
            aria-label={item.label}
            valueLabelDisplay="auto"
            onChangeCommitted={(e, value) => {
              if (formData) {
                const index = formData.findIndex(
                  (data: SliderData) => item.value === data.name
                );

                if (index === -1) {
                  // not found, so add to formData
                  const update = [
                    ...formData,
                    { name: item.value, value: value as number },
                  ];
                  onChange(update);
                } else {
                  // found, so replace
                  formData[index] = {
                    name: item.value,
                    value: value as number,
                  };

                  onChange(formData);
                }
                if (schema.slider_total_should_be_100) {
                  evaluateTotals();
                }
              } else {
                onChange([{ name: item.value, value: value as number }]);
              }
            }}
          />
        </Box>
      ))}

      {schema.slider_total_should_be_100 && formErrors.length ? (
        <Alert severity="error">{formErrors[0]}</Alert>
      ) : null}
    </>
  );
}

export default MultiSlider;
