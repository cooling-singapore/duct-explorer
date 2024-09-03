import { object, ref, string } from 'yup';

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expiry: number;
}

export interface LoginUser {
  email: string;
  password: string;
  next?: () => void;
}

export interface PasswordChangeForm {
  oldPassword: string;
  newPassword: string;
  newPasswordConfirmation: string;
}

export interface NameChangeForm {
  firstName: string;
  lastName: string;
}

export const PasswordValidationSchema = object().shape({
  oldPassword: string().required(),
  newPassword: string().required(),
  newPasswordConfirmation: string().oneOf(
    [ref('newPassword'), null],
    'Passwords must match'
  ),
});

export const UserNameValidationSchema = object().shape({
  firstName: string().required(),
  LastName: string().required(),
});

export interface Profile {
  login: string;
  name: string;
}
