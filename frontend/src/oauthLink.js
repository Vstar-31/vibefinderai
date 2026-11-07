// A top-level form establishes a first-party backend cookie without requiring
// third-party cookies. Only this short-lived transaction crosses the form;
// application credentials are sent exclusively in the Authorization header.
export async function startProviderLink(buildApiUrl, path, token) {
  const verifier = Array.from(crypto.getRandomValues(new Uint8Array(32)),
    byte => byte.toString(16).padStart(2, "0")).join("");
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  const challenge = Array.from(new Uint8Array(digest),
    byte => byte.toString(16).padStart(2, "0")).join("");
  const response = await fetch(buildApiUrl(`${path}/authorize`), {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ challenge }),
    cache: "no-store",
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || "Could not connect service");
  }
  const { ticket, start_url: startUrl } = await response.json();
  if (typeof ticket !== "string" || !/^[A-Za-z0-9_-]{43}$/.test(ticket)) {
    throw new Error("Invalid service connection response");
  }
  // The server returns its configured callback origin so a frontend reverse
  // proxy cannot leave the binding cookie on the wrong hostname.
  const target = new URL(startUrl);
  const local = ["localhost", "127.0.0.1", "[::1]"].includes(target.hostname);
  if ((target.protocol !== "https:" && !(local && target.protocol === "http:")) ||
      target.username || target.password || target.search || target.hash ||
      target.pathname !== `${path}/start`) {
    throw new Error("Invalid service connection destination");
  }
  const form = document.createElement("form");
  form.method = "POST";
  form.action = target.href;
  for (const [name, value] of Object.entries({ ticket, verifier })) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  try { form.submit(); } finally { form.remove(); }
}
