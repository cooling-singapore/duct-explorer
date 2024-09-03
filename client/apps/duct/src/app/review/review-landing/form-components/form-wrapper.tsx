import { IChangeEvent } from '@rjsf/core';
import { Form } from '@rjsf/mui';
import validator from '@rjsf/validator-ajv8';
import { useEffect, useState } from 'react';

interface FormWrapperProps {
  parameters: object;
  onChange: (form: IChangeEvent) => void;
}

const FormWrapper = (props: FormWrapperProps) => {
  const { parameters, onChange } = props;
  const [paramState, setParamState] = useState(parameters);
  const [paramForm, setParamForm] = useState({});

  // force form to rerender when params change
  useEffect(() => {
    setParamState(parameters);
  }, [parameters]);

  const formUpdated = (form: IChangeEvent) => {
    setParamForm(form.formData);
    onChange(form);
  };

  return (
    <Form
      schema={paramState}
      onChange={formUpdated}
      liveValidate
      showErrorList={false}
      formData={paramForm}
      validator={validator}
    >
      {/* Empty fragment allows us to remove the submit button from the rjsf form */}
      {/*  eslint-disable-next-line react/jsx-no-useless-fragment */}
      <></>
    </Form>
  );
};

export default FormWrapper;
