import { AppServerError, getUser, updateUser } from '@duct-core/data';
import { Box, Button, Paper, TextField, Typography } from '@mui/material';
import { AxiosError } from 'axios';
import { useSnackbar } from 'notistack';
import { SyntheticEvent, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from 'react-query';

import { PageTitle } from '@duct-core/ui';

function Profile() {
  const { enqueueSnackbar } = useSnackbar();
  const queryClient = useQueryClient();
  const [formErrors, setformErrors] = useState<string[]>(['']);
  const [passwordForm, setPasswordForm] = useState<{
    new: string;
    confirm: string;
  }>({ new: '', confirm: '' });

  const { data: profile } = useQuery(['getUser'], () => getUser(), {
    retry: false,
  });

  const updateNameMutation = useMutation(
    (data: { name: string }) => updateUser([], data.name),
    {
      onSuccess: () => {
        enqueueSnackbar(`Name updated`, { variant: 'success' });
        queryClient.invalidateQueries('getUser');
      },
    }
  );

  const updatePasswordMutation = useMutation(
    (data: { passwords: [pwO: string, pw1: string] }) =>
      updateUser(data.passwords, ''),
    {
      onSuccess: () => {
        enqueueSnackbar(`Password updated`, { variant: 'success' });
      },
      onError: (error: AxiosError<AppServerError>) => {
        const message = error?.response?.data.reason || 'Something went wrong';
        enqueueSnackbar(message, { variant: 'error' });
      },
    }
  );

  const handleSubmitNameChange = (e: SyntheticEvent) => {
    e.preventDefault();
    const target = e.target as typeof e.target & {
      name: { value: string };
    };
    updateNameMutation.mutate({ name: target.name.value });
  };

  const handleSubmitPasswordChange = (e: SyntheticEvent) => {
    e.preventDefault();

    if (formErrors.length === 0) {
      const target = e.target as typeof e.target & {
        oldPassword: { value: string };
        newPassword: { value: string };
        confirmPassword: {
          value: string;
          error: boolean;
          helperText: string;
        };
      };

      updatePasswordMutation.mutate({
        passwords: [target.oldPassword.value, target.newPassword.value],
      });
    }
  };

  const onPasswordChange = (isConfirm: boolean, input: string) => {
    if (input.length < 8) {
      setformErrors(() => ['Password should contain at least 8 characters']);
    } else if (isConfirm && input !== passwordForm.new) {
      setformErrors(() => ['Passwords do not match']);
    } else if (!isConfirm && input !== passwordForm.confirm) {
      setformErrors(() => ['Passwords do not match']);
    } else {
      setformErrors(() => []);
    }

    setPasswordForm((form) => ({
      ...form,
      ...(isConfirm && { confirm: input }),
      ...(!isConfirm && { new: input }),
    }));
  };

  return (
    <Box m={2}>
      <PageTitle title="Profile" />
      <Box
        sx={{
          '& .MuiTextField-root': { m: 1, width: '25ch' },
        }}
      >
        <Paper sx={{ p: 2, m: 2 }}>
          <Typography gutterBottom variant="h6">
            Your Profile
          </Typography>
          <form onSubmit={handleSubmitNameChange}>
            <Box my={2}>
              <TextField
                required
                label="Name"
                size="small"
                name="name"
                defaultValue={profile?.name}
              />
            </Box>
            <Button variant="contained" color="primary" type="submit">
              Update
            </Button>
          </form>
        </Paper>
        <Paper sx={{ p: 2, m: 2 }}>
          <Typography gutterBottom variant="h6">
            Change Password
          </Typography>
          <form onSubmit={handleSubmitPasswordChange}>
            <Box my={2}>
              <TextField
                required
                type="password"
                label="Old Password"
                size="small"
                name="oldPassword"
              />
              <TextField
                required
                type="password"
                value={passwordForm.new}
                label="New Password"
                size="small"
                name="newPassword"
                onChange={(event) =>
                  onPasswordChange(false, event.target.value)
                }
              />
              <TextField
                required
                type="password"
                value={passwordForm.confirm}
                label="Confirm Password"
                size="small"
                name="confirmPassword"
                onChange={(event) => onPasswordChange(true, event.target.value)}
                error={formErrors.length > 0}
                helperText={formErrors[0]}
              />
            </Box>
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={formErrors.length > 0}
            >
              Update Password
            </Button>
          </form>
        </Paper>
      </Box>
    </Box>
  );
}

export default Profile;
