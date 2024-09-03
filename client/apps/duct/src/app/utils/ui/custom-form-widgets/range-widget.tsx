import { Box, Slider, Typography } from '@mui/material';
import { WidgetProps } from '@rjsf/utils';
import { useEffect } from 'react';

function RangeWidget(props: WidgetProps) {
  const { onChange } = props;
  const schema = props.schema; //as unknown as SliderProps;

  useEffect(() => {
    onChange(schema.defaultValue || 0);
  }, []);

  return (
    <Box>
      {schema.title && (
        <Typography variant="body1" gutterBottom>
          {schema.title}
        </Typography>
      )}
      <Box
        sx={{
          height: schema.orientation === 'vertical' ? '100px' : '100%',
          my: schema.orientation === 'vertical' ? 2 : 0,
          mx: schema.orientation === 'vertical' ? 0 : 4,
        }}
        alignContent="center"
      >
        <Slider
          {...schema}
          onChangeCommitted={(e, value) => onChange(value)}
          name={props.name}
          id={props.id}
          sx={{
            '& .MuiSlider-markLabel': {
              fontSize: '0.65rem',
            },
          }}
          valueLabelDisplay="auto"
          defaultValue={props.value}
        />
      </Box>
    </Box>
  );
}

export default RangeWidget;
