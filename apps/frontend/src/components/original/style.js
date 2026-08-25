export function toReactStyle(styleText) {
  return Object.fromEntries(
    styleText
      .split(';')
      .filter(Boolean)
      .map((declaration) => {
        const separator = declaration.indexOf(':');
        const property = declaration.slice(0, separator).trim();
        const value = declaration.slice(separator + 1).trim();
        const camelProperty = property
          .replace(/^-webkit-/, 'Webkit-')
          .replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
        return [camelProperty, value];
      }),
  );
}
