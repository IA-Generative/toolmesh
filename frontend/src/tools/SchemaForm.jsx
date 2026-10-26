import Checkbox from "@codegouvfr/react-dsfr/Checkbox";
import Input from "@codegouvfr/react-dsfr/Input";
import Select from "@codegouvfr/react-dsfr/Select";
import { isRequired, kindOf, propertiesOf } from "./schema";

const INPUT_TYPES = { uri: "url", email: "email", date: "date" };

function Field({ name, prop, required, value, error, onChange }) {
  const kind = kindOf(prop);
  const label = required ? `${name} *` : name;
  const hintText = prop.description;
  const state = error ? { state: "error", stateRelatedMessage: error } : {};

  if (kind === "boolean") {
    return (
      <Checkbox
        options={[{ label: name, hintText, nativeInputProps: { checked: value, onChange: (e) => onChange(e.target.checked) } }]}
      />
    );
  }
  if (kind === "enum") {
    return (
      <Select label={label} hint={hintText} nativeSelectProps={{ value, onChange: (e) => onChange(e.target.value) }} {...state}>
        {!required && <option value="">—</option>}
        {prop.enum.map((v) => <option key={String(v)} value={String(v)}>{String(v)}</option>)}
      </Select>
    );
  }
  if (kind === "list" || kind === "json" || (kind === "string" && (prop.maxLength ?? 0) > 200)) {
    const extra = kind === "list" ? "Une valeur par ligne" : kind === "json" ? "JSON" : null;
    return (
      <Input
        label={label}
        hintText={[hintText, extra].filter(Boolean).join(" · ") || undefined}
        textArea
        nativeTextAreaProps={{ value, onChange: (e) => onChange(e.target.value), rows: kind === "string" ? 5 : 3, spellCheck: false }}
        {...state}
      />
    );
  }
  const numeric = kind === "number";
  return (
    <Input
      label={label}
      hintText={hintText}
      nativeInputProps={{
        value,
        onChange: (e) => onChange(e.target.value),
        type: numeric ? "number" : INPUT_TYPES[prop.format] ?? "text",
        step: prop.type === "integer" ? 1 : numeric ? "any" : undefined,
        min: prop.minimum,
        max: prop.maximum,
        placeholder: prop.default !== undefined ? String(prop.default) : undefined,
      }}
      {...state}
    />
  );
}

export default function SchemaForm({ schema, values, errors, onChange }) {
  const props = propertiesOf(schema);
  if (props.length === 0) return <p className="fr-text--sm">Cet outil n'attend aucun argument.</p>;
  return (
    <>
      {props.map(([key, prop]) => (
        <Field
          key={key}
          name={key}
          prop={prop}
          required={isRequired(schema, key)}
          value={values[key]}
          error={errors[key]}
          onChange={(v) => onChange(key, v)}
        />
      ))}
    </>
  );
}
