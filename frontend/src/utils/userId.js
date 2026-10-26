const URL_NAMESPACE = "6ba7b811-9dad-11d1-80b4-00c04fd430c8";

function uuidToBytes(uuid) {
  const hex = uuid.replace(/-/g, "");
  const bytes = new Uint8Array(16);

  for (let i = 0; i < 16; i++) {
    bytes[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }

  return bytes;
}

export async function getLocalUserId(authId) {
  const namespace = uuidToBytes(URL_NAMESPACE);
  const name = new TextEncoder().encode(`nutrigator:better-auth:${authId}`);

  const data = new Uint8Array(namespace.length + name.length);
  data.set(namespace);
  data.set(name, namespace.length);

  const hash = new Uint8Array(await crypto.subtle.digest("SHA-1", data));
  const bytes = hash.slice(0, 16);
  bytes[6] = (bytes[6] & 0x0f) | 0x50;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");

  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
