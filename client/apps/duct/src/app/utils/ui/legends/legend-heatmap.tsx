import { useEffect } from 'react';
import { Grid, Box, Paper, Typography, Stack } from '@mui/material';
import { select, max, min } from 'd3';
import SquareIcon from '@mui/icons-material/Square';

import { rgbToHex } from '../../helpers/arcgis-helpers';
import { LegendSubtype } from '@duct-core/data';

interface LegendLabel {
  color: number[] | string;
  label: string;
  value: number;
}

interface LegendHeatmapProps {
  title: string;
  labels: LegendLabel[];
  subtype: LegendSubtype;
}
const width = 300;
const height = 20;

export default function LegendHeatmap(props: LegendHeatmapProps) {
  const { title, labels, subtype } = props;

  return (
    <Paper sx={{ p: 2, maxWidth: width + 40 }}>
      <Grid container>
        <Typography variant="body2" sx={{ mb: 1 }}>
          {title}
        </Typography>
      </Grid>
      {subtype === LegendSubtype.DISCRETE ? (
        <DiscreteColorLegend labels={labels} />
      ) : (
        <ContinuousColorLegend labels={labels} />
      )}
    </Paper>
  );
}

function DiscreteColorLegend(props: { labels: LegendLabel[] }) {
  const { labels } = props;

  return (
    <Box overflow="auto" maxHeight="200px" minHeight="100px">
      {labels.map((label, index) => {
        // we add empty colors to legend to address index issues in the heatmap renderer. so dont show them
        if (label.label === '') {
          return null;
        }
        return (
          <Stack direction="row" key={`cat-${index}`}>
            <SquareIcon
              sx={{
                color: `rgb(${label.color[0]}, ${label.color[1]}, ${label.color[2]}, ${label.color[3]})`,
              }}
            />
            <Typography variant="caption">{label.label}</Typography>
          </Stack>
        );
      })}
    </Box>
  );
}

function ContinuousColorLegend(props: { labels: LegendLabel[] }) {
  const { labels } = props;

  useEffect(() => {
    select('.legend').empty();

    const data = labels.map((tick) => ({
      color: Array.isArray(tick.color)
        ? rgbToHex(tick.color[0], tick.color[1], tick.color[2])
        : tick.color,
      value: tick.value,
      label: tick.label,
    }));

    const legendExtent = [
      min(data, (data) => data.value) as number,
      max(data, (data) => data.value) as number,
    ];

    // const xScale = scaleLinear()
    //   .domain(legendExtent)
    //   .range([0, width - 40]);

    // const xTicks = data.map((d) => d.value);
    // const xAxis = axisBottom(xScale).tickValues(xTicks);
    // .tickFormat((d, i) => data[i].label);

    const svg = select('.legend')
      .append('svg')
      // .attr('width', width)
      .attr('height', height);

    const g = svg.append('g').attr('transform', 'translate(20, 0)');

    const defs = svg.append('defs');
    const linearGradient = defs
      .append('linearGradient')
      .attr('id', 'myGradient');
    linearGradient
      .selectAll('stop')
      .data(data)
      .enter()
      .append('stop')
      .attr(
        'offset',
        (d) =>
          ((d.value - legendExtent[0]) / (legendExtent[1] - legendExtent[0])) *
            100 +
          '%'
      )
      .attr('stop-color', (d) => d.color);

    g.append('rect')
      .attr('width', width - 40)
      .attr('height', 20)
      .style('fill', 'url(#myGradient)');

    g.append('g')
      // .call(xAxis)
      // .attr('transform', 'translate(0, 25)')
      .select('.domain')
      .remove();
  }, [labels]);

  return (
    <>
      <Grid container justifyContent="center">
        <div className="legend" />
      </Grid>
      <Grid container justifyContent="space-between">
        {labels.map((label, index) => {
          return (
            <Grid item key={index}>
              <Box fontSize={10}>{label.label}</Box>
            </Grid>
          );
        })}
      </Grid>
    </>
  );
}
