import { Redirect } from 'expo-router';

// Landing route for the `pear://magic-link?token=...` deep link.
//
// The token is verified by the AuthProvider's deep-link handler (it listens
// for inbound URLs and calls verifyMagicLink). This route just hands control
// back to the root routing gate, which redirects based on the now-committed
// session (or back to login if verification failed).
export default function MagicLinkRedirect() {
  return <Redirect href="/" />;
}
