import React from "react";

const SYNTHETIC_DATASET_LABEL = "[DEMO LAB / SYNTHETIC]";

function readableRiskStatus(value: string | undefined): string {
  if (!value) return "Not reported";
  if (value === SYNTHETIC_DATASET_LABEL) return value;
  return value
    .replace(/^\[|\]$/g, "")
    .replace(/[_-]+/g, " ")
    .toLowerCase()
    .replace(/(^|[\s/])[a-z]/g, (part) => part.toUpperCase());
}

type RiskStatusValueProps = {
  value: string | undefined;
  as?: "strong" | "span";
};

export const RiskStatusValue: React.FC<RiskStatusValueProps> = ({ value, as = "span" }) => {
  const Element = as;
  return <Element>{readableRiskStatus(value)}</Element>;
};
