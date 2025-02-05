import Typography from '@mui/material/Typography';

export interface PageTitleProps {
  title?: string;
  description?: string;
}

export function PageTitle(props: PageTitleProps) {
  const { title, description } = props;
  return (
    <>
      {title && (
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
      )}
      {description && (
        <Typography variant="body2" gutterBottom>
          {description}
        </Typography>
      )}
    </>
  );
}

export default PageTitle;
