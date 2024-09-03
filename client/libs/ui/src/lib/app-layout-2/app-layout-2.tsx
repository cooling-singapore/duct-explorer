import { useState, MouseEvent, useEffect } from 'react';
import IconButton from '@mui/material/IconButton';
import MenuIcon from '@mui/icons-material/Menu';
import {
  AppBar,
  Box,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Stack,
  styled,
  ToggleButton,
  ToggleButtonGroup,
  Toolbar,
  Typography,
  useTheme,
} from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';

import { SideBarMenuItem, SideBarSettingItem } from '@duct-core/data';

export interface AppLayout2Props {
  children: React.ReactNode;
  appTitle: string;
  menuItems: SideBarMenuItem[];
  settingItems?: SideBarSettingItem[];
  logoPath: string;
  projectName?: string;
}

const toolbarHeight = 64;
const Logo = styled('img')(`width: 180px`);

export function AppLayout2(props: AppLayout2Props) {
  const { menuItems, settingItems, projectName } = props;
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useTheme();
  const initiaPath = location.pathname.split('/')[2];
  const [activeRoute, setActiveRoute] = useState<string>(
    `${initiaPath === '' ? 'build' : initiaPath}`
  );
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  useEffect(() => {
    setActiveRoute(`${initiaPath === '' ? 'build' : initiaPath}`);
  }, [initiaPath]);

  const handleClick = (event: React.MouseEvent<HTMLButtonElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleRoute = (event: MouseEvent<HTMLElement>, route: string) => {
    if (route !== null) {
      navigate(route);
    }
  };

  return (
    <div>
      <AppBar position="fixed">
        <Toolbar sx={{ height: toolbarHeight }}>
          <IconButton
            edge="start"
            color="inherit"
            aria-label="menu"
            onClick={handleClick}
            size="large"
          >
            <MenuIcon />
          </IconButton>
          {projectName && (
            <Typography sx={{ fontWeight: 'bold' }}>{projectName}</Typography>
          )}
          <Box
            sx={{
              display: 'flex',
              flexGrow: 1,
              justifyContent: 'center',
              height: theme.spacing(8),
            }}
          >
            <ToggleButtonGroup
              value={activeRoute}
              exclusive
              onChange={handleRoute}
            >
              {menuItems &&
                menuItems.map((item: SideBarMenuItem) => (
                  <ToggleButton
                    key={item.key}
                    value={item.route}
                    disabled={item.disabled}
                    selected={activeRoute === item.route}
                    sx={[
                      {
                        minWidth: 120,
                        color: item.disabled
                          ? `${theme.palette.grey[600]} !important`
                          : theme.palette.grey[400],
                        pt: theme.spacing(2),
                      },
                      activeRoute === item.route && {
                        color: `${theme.palette.primary.contrastText} !important`,
                        borderBottom: `3px solid ${theme.palette.secondary.main}`,
                        backgroundColor: `${theme.palette.primary.dark} !important`,
                      },
                    ]}
                  >
                    <Stack spacing={1} direction="row">
                      <div>{item.icon}</div>
                      <div>{item.text}</div>
                    </Stack>
                  </ToggleButton>
                ))}
            </ToggleButtonGroup>
          </Box>
          <Logo src={props.logoPath} alt="logo" />
        </Toolbar>
      </AppBar>
      <Box
        sx={{
          marginTop: `${toolbarHeight}px`,
          overflow: 'auto',
          height: `calc(100vh - ${toolbarHeight}px)`,
        }}
      >
        {props.children}
      </Box>
      <div>
        <Menu
          anchorEl={anchorEl}
          keepMounted
          open={Boolean(anchorEl)}
          onClose={handleClose}
        >
          {settingItems &&
            settingItems.map((item) => (
              <MenuItem
                key={item.key}
                onClick={() => {
                  item.next();
                  handleClose();
                }}
              >
                <ListItemIcon>{item.icon}</ListItemIcon>
                <ListItemText color="text.primary">{item.text}</ListItemText>
              </MenuItem>
            ))}
        </Menu>
      </div>
    </div>
  );
}

export default AppLayout2;
