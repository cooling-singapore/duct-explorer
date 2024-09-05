import { Story, Meta } from '@storybook/react';
import SignIn, { SignInProps } from './sign-in';

export default {
  component: SignIn,
  title: 'Sign In',
} as Meta;

const Template: Story<SignInProps> = (args) => <SignIn {...args} />;

export const Primary = Template.bind({});
Primary.args = {
  imageUrl: 'https://source.unsplash.com/random',
  appTitle: 'Storybook App',
  appDescription: 'Signin to storybook app'
};
