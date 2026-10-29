import React from "react";

interface FieldShellProps {
  id: string;
  label: string;
  hint?: React.ReactNode;
  error?: string | null;
  required?: boolean;
  children: React.ReactNode;
  className?: string;
}

/** Tabler form group: form-label, control, form-hint, invalid-feedback. */
const FieldShell: React.FC<FieldShellProps> = ({ id, label, hint, error, required, children, className }) => (
  <div className={className ?? "mb-3"}>
    <label className={["form-label", required ? "required" : ""].filter(Boolean).join(" ")} htmlFor={id}>{label}</label>
    {children}
    {hint && <small className="form-hint" id={`${id}-hint`}>{hint}</small>}
    {error && <div className="invalid-feedback d-block" id={`${id}-error`}>{error}</div>}
  </div>
);

function describedBy(id: string, hint?: React.ReactNode, error?: string | null): string | undefined {
  const ids = [hint ? `${id}-hint` : "", error ? `${id}-error` : ""].filter(Boolean);
  return ids.length ? ids.join(" ") : undefined;
}

function controlClass(base: string, error?: string | null, extra?: string): string {
  return [base, error ? "is-invalid" : "", extra ?? ""].filter(Boolean).join(" ");
}

type InputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "id"> & {
  label: string;
  hint?: React.ReactNode;
  error?: string | null;
  id?: string;
  groupClassName?: string;
};

export const TextField: React.FC<InputProps> = ({ label, hint, error, id, required, className, groupClassName, ...rest }) => {
  const generated = React.useId();
  const fieldId = id ?? generated;
  return (
    <FieldShell id={fieldId} label={label} hint={hint} error={error} required={required} className={groupClassName}>
      <input
        id={fieldId}
        className={controlClass("form-control", error, className)}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, hint, error)}
        {...rest}
      />
    </FieldShell>
  );
};

type SelectProps = Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "id"> & {
  label: string;
  hint?: React.ReactNode;
  error?: string | null;
  id?: string;
  groupClassName?: string;
  children: React.ReactNode;
};

export const SelectField: React.FC<SelectProps> = ({ label, hint, error, id, required, children, className, groupClassName, ...rest }) => {
  const generated = React.useId();
  const fieldId = id ?? generated;
  return (
    <FieldShell id={fieldId} label={label} hint={hint} error={error} required={required} className={groupClassName}>
      <select
        id={fieldId}
        className={controlClass("form-select", error, className)}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, hint, error)}
        {...rest}
      >
        {children}
      </select>
    </FieldShell>
  );
};

type TextAreaProps = Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> & {
  label: string;
  hint?: React.ReactNode;
  error?: string | null;
  id?: string;
  mono?: boolean;
  groupClassName?: string;
};

export const TextAreaField: React.FC<TextAreaProps> = ({ label, hint, error, id, required, mono = false, className, groupClassName, ...rest }) => {
  const generated = React.useId();
  const fieldId = id ?? generated;
  return (
    <FieldShell id={fieldId} label={label} hint={hint} error={error} required={required} className={groupClassName}>
      <textarea
        id={fieldId}
        className={controlClass("form-control", error, [mono ? "font-monospace" : "", className ?? ""].join(" ").trim())}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(fieldId, hint, error)}
        {...rest}
      />
    </FieldShell>
  );
};

/** Tabler form-check; pass type="radio" for a radio option. */
export const Checkbox: React.FC<Omit<React.InputHTMLAttributes<HTMLInputElement>, "type"> & { label: React.ReactNode; type?: "checkbox" | "radio" }> = ({
  label, id, type = "checkbox", className, ...rest
}) => {
  const generated = React.useId();
  const fieldId = id ?? generated;
  return (
    <div className={["form-check", className ?? ""].filter(Boolean).join(" ")}>
      <input type={type} id={fieldId} className="form-check-input" {...rest} />
      <label className="form-check-label" htmlFor={fieldId}>{label}</label>
    </div>
  );
};
