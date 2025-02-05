import {
  FormControl,
  FormControlLabel,
  FormLabel,
  Radio,
  RadioGroup,
  Typography,
} from '@mui/material';
import { WidgetProps } from '@rjsf/utils';

function RadioWidget(props: WidgetProps) {
  const { onChange } = props;
  const schema = props.schema;

  return (
    <FormControl>
      <FormLabel id={props.id}>{props.label}</FormLabel>
      <RadioGroup
        {...schema}
        aria-labelledby={props.id}
        name={props.name}
        onChange={(e, value) => onChange(value)}
        defaultValue={props.value}
      >
        {props.options.enumOptions?.map((option, index) => {
          return (
            <div key={`container-${props.id}-${index}`}>
              <FormControlLabel
                id={`${props.id}-${index}`}
                value={option.value}
                control={<Radio />}
                label={option.label}
              />
              <Typography variant="body2" sx={{ color: 'grey.600' }}>
                {option.schema?.description}
              </Typography>
            </div>
          );
        })}
      </RadioGroup>
    </FormControl>
  );
}

export default RadioWidget;
