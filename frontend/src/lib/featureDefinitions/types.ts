export type FeatureDefinition = {
  key: string;
  // null => standalone feature with no parent-module prerequisite (always toggleable).
  parent_module: string | null;
  label: string;
};
