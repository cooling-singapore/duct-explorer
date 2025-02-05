import { TooltipProps, tooltipClasses, Tooltip, styled } from '@mui/material';

const HtmlTooltip = styled(({ className, ...props }: TooltipProps) => (
  <Tooltip {...props} classes={{ popper: className }} />
))(() => ({
  [`& .${tooltipClasses.tooltip}`]: {
    backgroundColor: 'transparent',
    padding: 0,
    border: '1px solid #dadde9',
  },
}));

export default HtmlTooltip;
