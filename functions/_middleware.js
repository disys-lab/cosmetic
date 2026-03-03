/**
 * Cloudflare Pages middleware — HTTP Basic Auth.
 *
 * Protects the entire docs site with a shared password so that
 * access does not require reviewers to identify themselves.
 *
 * Set the secret in the Cloudflare Pages dashboard:
 *   Settings → Environment variables → Add variable (secret)
 *   Name: DOCS_PASSWORD
 *
 * Share the following with reviewers (e.g. via the paper submission system):
 *   URL:      https://cosmetic.pages.dev
 *   Password: <value of DOCS_PASSWORD>
 *   (username can be anything)
 */
export async function onRequest({ request, env, next }) {
  const auth = request.headers.get("Authorization");

  if (auth) {
    const [scheme, encoded] = auth.split(" ");
    if (scheme === "Basic" && encoded) {
      const decoded = atob(encoded);
      const colonIdx = decoded.indexOf(":");
      const pass = decoded.slice(colonIdx + 1);
      if (pass === env.DOCS_PASSWORD) {
        return next();
      }
    }
  }

  return new Response("Unauthorized", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="CoSMeTIC Docs", charset="UTF-8"',
      "Content-Type": "text/plain",
    },
  });
}
