import { SvgIconProps } from '@mui/material/SvgIcon';

export interface SideBarItem {
  text: string;
  key: string;
  icon: React.ReactElement<SvgIconProps>;
  disabled?: boolean;
}

export interface SideBarMenuItem extends SideBarItem {
  route: string;
}

export interface SideBarSettingItem extends SideBarItem {
  next: () => void;
}
