import { useState } from 'react';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import { useSnackbar } from 'notistack';
import { useMutation, useQueryClient } from 'react-query';
import { IconButton, Menu, MenuItem } from '@mui/material';
import { useNavigate } from 'react-router-dom';

import { Scene, SceneType, deleteScene } from '@duct-core/data';
import { Confirmation, JsonDialog } from '@duct-core/ui';
import { useScene } from '../../../context/scene.context';

interface SceneMenuProps {
  scene: Scene;
  projectId: string;
}

function SceneMenu(props: SceneMenuProps) {
  const { scene, projectId } = props;
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const sceneContext = useScene();
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [showSceneDetail, setshowSceneDetail] = useState(false);

  const sceneDelteMutation = useMutation(
    () => deleteScene(projectId, scene.id),
    {
      onSuccess: () => {
        enqueueSnackbar(`Scene deleted successfully`, { variant: 'success' });
        //invalidate getScenes so list gets updated
        queryClient.invalidateQueries('getScenes');
      },
    }
  );

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleDelete = () => {
    handleClose();
    sceneDelteMutation.mutate();
  };

  const handleUseAsTemplate = () => {
    sceneContext.setContext((prevState) => {
      const copy = { ...prevState };
      copy.sceneType = SceneType.Islandwide;
      copy.module_settings = scene.module_settings;
      copy.zoneVersions = scene.caz_alt_mapping;
      return copy;
    });
    navigate('/app/build/workflow');
  };

  return (
    <>
      <IconButton size="small" aria-label="More" onClick={handleClick}>
        <MoreVertIcon />
      </IconButton>
      <Menu
        id="simple-menu"
        anchorEl={anchorEl}
        keepMounted
        open={Boolean(anchorEl)}
        onClose={handleClose}
      >
        <MenuItem>
          <Confirmation
            disabled={scene.name === 'Default'}
            text="Deleting this scene will delete all associated results and outputs. Are you sure you want to delete?"
            confirmButtonText="Yes"
            cancelButtonText="No"
            onConfirm={() => handleDelete()}
            onCancel={handleClose}
            button={<>Delete Scene</>}
          />
        </MenuItem>
        <MenuItem
          onClick={() => {
            setshowSceneDetail(true);
            handleClose();
          }}
        >
          Scene Properties
        </MenuItem>
        <MenuItem
          onClick={() => {
            handleUseAsTemplate();
            handleClose();
          }}
        >
          Use Scene as Template
        </MenuItem>
      </Menu>
      <JsonDialog
        open={showSceneDetail}
        data={scene}
        title="Scene Properties"
        onClose={() => setshowSceneDetail(false)}
      />
    </>
  );
}

export default SceneMenu;
