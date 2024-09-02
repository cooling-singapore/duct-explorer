import { Story, Meta } from '@storybook/react';
import PageTitle, { PageTitleProps } from './page-title';

export default {
  component: PageTitle,
  title: 'PageTitle',
} as Meta;

const Template: Story<PageTitleProps> = (args) => <PageTitle {...args} />;

export const Default = Template.bind({});

Default.args = {
  title: 'Lorem ipsum dolor sit amet',
  description:
    'consectetur adipiscing elit. Phasellus acimperdiet metus, ut tempor arcu.',
};
