import axios from 'axios';

import { LoginResponse, LoginUser, Profile } from './user.model';

export const signIn = (credentials: LoginUser) => {
  const params = new URLSearchParams();
  params.append('username', credentials.email);
  params.append('password', credentials.password);

  return axios.post<LoginResponse>('/token', params);
};

//TODO: wait for BE to implement
export const signOut = () => axios.post(`/logout`);

export const updateUser = (password: string[], name: string) =>
  axios.put(`/user/profile`, {
    ...(password.length && { password }),
    ...(name !== '' && { name }),
  });

export const getUser = (): Promise<Profile> =>
  axios.get(`/user/profile`).then((res) => res.data);
