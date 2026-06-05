// Type augmentation for react-syntax-highlighter ESM prism-light module.
// The module exports PrismLight both as default and as a named export, but the
// @types package only declares the default export. This augmentation adds the
// named PrismLight export and its registerLanguage static method.

/* eslint-disable @typescript-eslint/no-explicit-any */
declare module 'react-syntax-highlighter/dist/esm/prism-light' {
  interface PrismLightComponent {
    registerLanguage(lang: string, langFn: unknown): void;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (props: any): JSX.Element;
  }

  const PrismLight: PrismLightComponent;
  export { PrismLight };
  export default PrismLight;
}
/* eslint-enable @typescript-eslint/no-explicit-any */
