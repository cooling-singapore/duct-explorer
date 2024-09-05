import { WidgetProps } from '@rjsf/utils';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

function MarkdownField(props: WidgetProps) {
  return <Markdown remarkPlugins={[remarkGfm]}>{props.schema.data}</Markdown>;
}

export default MarkdownField;
