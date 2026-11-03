// Kept apart from CardRoutes so the route switch can test a path without loading the pages.
const CARD_PATH = /^\/(?:verify\/c\/[^/]+|o\/[^/]+\/ids\/[^/]+|(?:m\/[^/]+\/)?member\/cards(?:\/accept)?)\/?$/;

export function isCardPath(pathname: string) {
  return CARD_PATH.test(pathname);
}
