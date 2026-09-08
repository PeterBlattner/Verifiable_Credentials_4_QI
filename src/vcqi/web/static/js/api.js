// Every call the interface makes to the demonstration server.
//
// These are the same routes a verifier would use: fetching a document by its address,
// asking for a credential to be verified under stated conditions, or asking whether a
// hypothetical result falls inside a published capability.

async function request(path, options) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (error) {
      // The server did not send JSON; the status text is all we have.
    }
    throw new Error(`${path}: ${detail}`);
  }
  return response.json();
}

function post(path, body) {
  return request(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
}

export const api = {
  world: () => request('/api/world'),
  content: () => request('/api/content'),
  actor: (did) => request(`/api/actor/${did}`),
  credential: (name) => request(`/api/credential/${name}`),
  document: (url) => request(`/api/document?url=${encodeURIComponent(url)}`),
  verify: (options) => post('/api/verify', options),
  tamper: (key) => post(`/api/tamper/${key}`, {}),
  scope: (options) => post('/api/scope', options),
  uncertainty: (options) => post('/api/uncertainty', options),
  combine: (options) => post('/api/combine', options),
  deriveKey: (options) => post('/api/keys/derive', options),
  signMessage: (options) => post('/api/keys/sign', options),
  verifySignature: (options) => post('/api/keys/verify', options),
  issueAsReader: (options) => post('/api/keys/issue', options),
  gtc: () => request('/api/gtc'),
  infrastructure: () => request('/api/infrastructure'),
  harmonisation: () => request('/api/harmonisation'),
  portability: () => request('/api/portability'),
  workflows: () => request('/api/exchange/workflows'),
  openExchange: (workflowId) => post(`/workflows/${workflowId}/exchanges`, {}),
  // The two turns of an exchange are the same POST to the same URL. What distinguishes
  // them is the body, which is why there is one call here and not two.
  exchangeTurn: (workflowId, exchangeId, body) =>
    post(`/workflows/${workflowId}/exchanges/${exchangeId}`, body || {}),
  // Not part of VCALM. The browser has to play a holder whose key lives on the server,
  // so it asks the server to sign on the holder's behalf; chapter 12 says so plainly.
  presentAs: (workflowId, exchangeId) =>
    post(`/api/exchange/${workflowId}/${exchangeId}/present`, {}),
  // Dependency data is XML or a binary blob, so it comes back as text rather than JSON.
  uncertaintyData: async (url) => {
    const response = await fetch(`/api/uncertainty-data?url=${encodeURIComponent(url)}`);
    if (!response.ok) throw new Error(`${url}: ${response.statusText}`);
    return {
      mediaType: response.headers.get('content-type') || 'application/octet-stream',
      bytes: (await response.clone().arrayBuffer()).byteLength,
      text: await response.text(),
    };
  },
};
