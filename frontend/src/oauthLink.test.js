import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { startProviderLink } from "./oauthLink.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; delete globalThis.document; });

function browserFixture(response) {
  const requests = [];
  const submitted = [];
  globalThis.fetch = async (url, options) => {
    requests.push({ url, options });
    return { ok: true, json: async () => response };
  };
  globalThis.document = {
    body: { appendChild() {} },
    createElement(tag) {
      return { tag, children: [], appendChild(child) { this.children.push(child); },
        submit() { submitted.push(this); }, remove() {} };
    },
  };
  return { requests, submitted };
}

test("proxy API fetch keeps JWT in header; top-level form uses callback host and verifier", async () => {
  const fixture = browserFixture({ ticket: "t".repeat(43), start_url: "https://backend.example/api/spotify/start" });
  await startProviderLink(path => path, "/api/spotify", "app-login-secret");
  assert.equal(fixture.requests.length, 1);
  const { url, options } = fixture.requests[0];
  assert.equal(url, "/api/spotify/authorize");
  assert.equal(options.method, "POST");
  assert.equal(options.headers.Authorization, "Bearer app-login-secret");
  const form = fixture.submitted[0];
  assert.equal(form.method, "POST");
  assert.equal(form.action, "https://backend.example/api/spotify/start");
  const fields = Object.fromEntries(form.children.map(input => [input.name, input.value]));
  assert.deepEqual(Object.keys(fields), ["ticket", "verifier"]);
  assert.equal(fields.ticket, "t".repeat(43));
  assert.match(fields.verifier, /^[0-9a-f]{64}$/);
  assert.equal(JSON.parse(options.body).challenge, createHash("sha256").update(fields.verifier).digest("hex"));
  assert.ok(!JSON.stringify(fields).includes("app-login-secret"));
  assert.ok(!url.includes("app-login-secret"));
});

test("each connection attempt uses a fresh browser verifier", async () => {
  const fixture = browserFixture({ ticket: "t".repeat(43), start_url: "https://backend.example/api/services/youtube/start" });
  await startProviderLink(p => p, "/api/services/youtube", "secret");
  await startProviderLink(p => p, "/api/services/youtube", "secret");
  assert.notEqual(fixture.requests[0].options.body, fixture.requests[1].options.body);
});

for (const start_url of ["http://backend.example/api/spotify/start", "https://backend.example/wrong",
  "https://user:password@backend.example/api/spotify/start", "https://backend.example/api/spotify/start?secret=1",
  "javascript:alert(1)"]) {
  test(`reject unsafe connection destination ${start_url}`, async () => {
    const fixture = browserFixture({ ticket: "t".repeat(43), start_url });
    await assert.rejects(startProviderLink(p => p, "/api/spotify", "secret"));
    assert.equal(fixture.submitted.length, 0);
  });
}

test("server authorization failure never submits a form", async () => {
  const fixture = browserFixture({});
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: "Invalid token" }) });
  await assert.rejects(startProviderLink(p => p, "/api/spotify", "bad"), /Invalid token/);
  assert.equal(fixture.submitted.length, 0);
});
