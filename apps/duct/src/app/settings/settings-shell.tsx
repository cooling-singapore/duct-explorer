import { useEffect, useState } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Drawer,
  Divider,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  styled,
} from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import FolderIcon from '@mui/icons-material/Folder';
import PersonIcon from '@mui/icons-material/Person';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { useAuth } from '../context/auth.context';
import { environment } from '../../environments/environment';

interface SettingsShellProps {
  children: React.ReactNode;
}

function SettingsShell(props: SettingsShellProps) {
  const { children } = props;
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const initiaPath = location.pathname.split('/')[2];
  const [activeRoute, setActiveRoute] = useState<string>(
    `${initiaPath === '' ? 'projects' : initiaPath}`
  );

  const drawerWidth = 240;
  const toolbarHeight = 64;
  const Logo = styled('img')(`width: 180px;`);
  const divider = { borderColor: 'grey.600' };
  const iconStyle = { color: 'primary.contrastText' };
  const listItemStyle = {
    '&.Mui-selected': {
      backgroundColor: 'primary.dark',
      borderLeft: `3px solid`,
      borderLeftColor: 'secondary.main',
    },
  };

  useEffect(() => {
    setActiveRoute(`${initiaPath === '' ? 'projects' : initiaPath}`);
  }, [initiaPath]);

  const signOut = () => {
    auth?.signout(() => navigate('/login'));
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <AppBar
        position="fixed"
        sx={{ width: `calc(100% - ${drawerWidth}px)`, ml: `${drawerWidth}px` }}
      >
        <Toolbar sx={{ height: toolbarHeight }}>
          <Logo
            sx={{ marginLeft: 'auto' }}
            src={environment.APP_LOGO}
            alt="logo"
          />
        </Toolbar>
      </AppBar>
      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            backgroundColor: 'primary.main',
            color: 'primary.contrastText',
          },
        }}
        variant="permanent"
        anchor="left"
        color="primary"
      >
        <Toolbar />
        <Divider sx={divider} />
        <List>
          <ListItem disablePadding>
            <ListItemButton
              component={Link}
              to="projects"
              selected={activeRoute === 'projects'}
              sx={listItemStyle}
            >
              <ListItemIcon>
                <FolderIcon sx={iconStyle} />
              </ListItemIcon>
              <ListItemText primary="Projects" />
            </ListItemButton>
          </ListItem>
          <ListItem disablePadding>
            <ListItemButton
              component={Link}
              to="profile"
              selected={activeRoute === 'profile'}
              sx={listItemStyle}
            >
              <ListItemIcon>
                <PersonIcon sx={iconStyle} />
              </ListItemIcon>
              <ListItemText primary="Profile" />
            </ListItemButton>
          </ListItem>
        </List>
        <Box sx={{ marginTop: 'auto' }}>
          <Divider sx={divider} />
          <List>
            <ListItem disablePadding onClick={signOut} data-testid="signout">
              <ListItemButton>
                <ListItemIcon>
                  <LogoutIcon sx={iconStyle} />
                </ListItemIcon>
                <ListItemText primary="Signout" />
              </ListItemButton>
            </ListItem>
          </List>
        </Box>
      </Drawer>
      <Box
        sx={{
          overflow: 'hidden',
          height: `calc(100vh - ${toolbarHeight}px)`,
          width: `calc(100% - ${drawerWidth}px)`,
          marginTop: `${toolbarHeight}px`,
        }}
      >
        <Box sx={{ height: '100%' }}>{children}</Box>
      </Box>
    </Box>
  );
}

export default SettingsShell;
