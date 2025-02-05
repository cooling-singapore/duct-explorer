import { useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';

import { LoginUser } from '@duct-core/data';
import { SignIn } from '@duct-core/ui';
import { useAuth } from '../context/auth.context';
import { environment } from '../../environments/environment';

export function Signin() {
  const navigate = useNavigate();
  const auth = useAuth();
  const { enqueueSnackbar } = useSnackbar();

  const login = (credentials: LoginUser) => {
    if (credentials.email && credentials.password) {
      credentials.next = () => navigate('/manage/projects');
      auth?.signin(credentials);
    } else {
      enqueueSnackbar('Email and password are required', { variant: 'error' });
    }
  };

  return (
    <SignIn
      onSubmit={login}
      imageUrl={environment.APP_LANDING_IMAGE}
      appTitle={environment.APP_TITLE}
      appDescription={environment.APP_DESCRIPTION}
      isLoading={auth?.isLoading || false}
    />
  );
}

export default Signin;
