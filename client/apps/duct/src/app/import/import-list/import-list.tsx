import { useState } from 'react';
import { useQuery } from 'react-query';
import { Link } from 'react-router-dom';
import {
  Box,
  Divider,
  List,
  ListItemText,
  ListItemSecondaryAction,
  Button,
  Skeleton,
  Stack,
  ListItemButton,
} from '@mui/material';

import { EmptyState, PageTitle } from '@duct-core/ui';
import { getImports, DataSet } from '@duct-core/data';
import { useProject } from '../../context/project.context';
import { useImportLanding } from '../../context/import-landing.context';
import ImportMenu from './import-menu';

function ImportList() {
  const importLandingContext = useImportLanding();
  const projectContext = useProject();
  const projectId = projectContext?.project?.id || '';

  // if navigation is from a successful import, selected_id param wll be set
  const params = new URLSearchParams(window.location.search);
  const paramImportId = params.get('selected_id') || undefined;

  const [selectedObjId, setSelectedObjId] = useState<string | undefined>(
    paramImportId
  );

  const { data, error, isLoading } = useQuery<DataSet, Error>(
    ['getImports', projectId],
    () => getImports(projectId),
    {
      retry: false,
      enabled: projectId !== '',
      onSuccess(data) {
        if (!selectedObjId && data.available.length) {
          // if param id is not set, pick the first item
          onImportSelected(data.available[0].obj_id);
        } else if (selectedObjId && data.available.length) {
          // if param id is set, select that
          onImportSelected(selectedObjId);
        }
      },
    }
  );

  if (error) {
    console.error(error || 'ImportList: something went wrong');
    return null;
  }

  const onImportSelected = (id: string) => {
    setSelectedObjId(id);
    importLandingContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.selectedImportId = id;
      return copy;
    });
  };

  return (
    <Box m={4}>
      <PageTitle title="Library" />
      <Divider />

      {isLoading ? (
        <Stack direction="column" spacing={1}>
          <Skeleton variant="rectangular" height={30} />
          <Skeleton variant="rectangular" height={30} />
        </Stack>
      ) : data && data.available && data.available.length ? (
        <List dense disablePadding>
          {data.available.map((libItem, index) => (
            <ListItemButton
              key={libItem.obj_id}
              onClick={() => onImportSelected(libItem.obj_id)}
              selected={
                selectedObjId === ''
                  ? index === 0
                  : selectedObjId === libItem.obj_id
              }
            >
              <ListItemText
                primary={libItem.name}
                secondary={libItem.type_label}
              />
              <ListItemSecondaryAction>
                <ImportMenu projectId={projectId} libItem={libItem} />
              </ListItemSecondaryAction>
            </ListItemButton>
          ))}
        </List>
      ) : (
        <Box m={6}>
          <EmptyState message="No imports yet. Click on the New Import button below to get started" />
        </Box>
      )}

      <Box my={8}>
        <Button
          variant="contained"
          color="secondary"
          fullWidth
          component={Link}
          to="workflow"
          data-testid="new-import"
        >
          New Import
        </Button>
      </Box>
    </Box>
  );
}

export default ImportList;
