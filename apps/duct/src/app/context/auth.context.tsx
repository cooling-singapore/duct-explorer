import axios, { AxiosError, AxiosResponse } from 'axios';
import { NextFunction } from 'express';
import { useContext, createContext, useState, useEffect } from 'react';
import { useMutation } from 'react-query';
import { Navigate, RouteProps, useNavigate } from 'react-router-dom';
import { useSnackbar } from 'notistack';

import { environment } from '../../environments/environment';
import { signIn, LoginUser } from '@duct-core/data';
import { useProject } from './project.context';

interface IAuthContext {
  token: string | undefined;
  signin: (credentials: LoginUser) => void;
  signout: (next: NextFunction) => void;
  isLoading: boolean;
}

const authContext = createContext<IAuthContext | undefined>(undefined);
authContext.displayName = 'AuthContext';

export function useAuth() {
  return useContext(authContext);
}

export function ProvideAuth({ children }: RouteProps) {
  const auth = useProvideAuth();
  return <authContext.Provider value={auth}>{children}</authContext.Provider>;
}

function useProvideAuth() {
  const sessionToken = sessionStorage.getItem('token');
  const [token, setToken] = useState(sessionToken || undefined);
  const { enqueueSnackbar } = useSnackbar();
  const navigate = useNavigate();
  const projectContext = useProject();

  useEffect(() => {
    axios.defaults.baseURL = environment.apiHost;
  }, []);

  useEffect(() => {
    if (token) {
      axios.defaults.headers.common = {
        Authorization: `bearer ${token}`,
      };
    }
  }, [token]);

  // global interceptor to kick the user out if not authenticated
  axios.interceptors.response.use(
    (response) => response, // leave 2xx responses alone
    (error: AxiosError) => {
      // Any status codes that falls outside the range of 2xx cause this function to trigger
      // kick the user out for any auth errors
      if (
        error.response?.status &&
        [401, 403].includes(error.response.status)
      ) {
        projectContext?.setProject(undefined); // clear project from context too
        signout(() => navigate('/login')); // signout clears session data (auth token and project selection)
      }

      return Promise.reject(error);
    }
  );

  const { isLoading, mutate } = useMutation((credentials: LoginUser) =>
    signIn(credentials)
      .then((res: AxiosResponse) => {
        axios.defaults.headers.common = {
          Authorization: `bearer ${res.data.access_token}`,
        };

        setToken(res.data.access_token);
        sessionStorage.setItem('token', res.data.access_token);

        if (credentials.next) {
          credentials.next();
        }
      })
      .catch((err) => {
        if (err.response) {
          // creddential related
          enqueueSnackbar(
            err.response.data.detail || 'Incorrect email or password',
            { variant: 'error' }
          );
        } else {
          // network related
          console.error(err.message);
          enqueueSnackbar('Sorry, something went wrong', { variant: 'error' });
        }
      })
  );

  const signin = (credentials: LoginUser) => {
    mutate(credentials);
  };

  const signout = (next: NextFunction) => {
    setToken(undefined);
    sessionStorage.clear(); // clears token & project data
    if (next) {
      next();
    }
  };

  return {
    token,
    signin,
    signout,
    isLoading,
  };
}

export function PrivateRoute({ children }: RouteProps) {
  const auth = useAuth();

  return auth?.token ? (
    <div>{children}</div>
  ) : (
    <Navigate
      to={{
        pathname: '/login',
      }}
    />
  );
}
