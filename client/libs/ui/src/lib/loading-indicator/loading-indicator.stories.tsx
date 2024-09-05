import { Story, Meta } from '@storybook/react';
import LoadingIndicator from './loading-indicator';

export default {
  component: LoadingIndicator,
  title: 'LoadingIndicator',
} as Meta;

const Template: Story = () => <LoadingIndicator />;

export const Default = Template.bind({});

