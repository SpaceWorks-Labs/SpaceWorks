/**
 * Just enough CIDR arithmetic for the staff IP allow-list editor: parse an entry and tell
 * whether one network sits inside another. The server (`ipaddress`) stays the authority;
 * this only stops an obviously wrong or too-loose entry before the request.
 */
export type Network = { version: 4 | 6; base: bigint; prefix: number };

function parseV4(address: string): bigint | null {
  const parts = address.split(".");
  if (parts.length !== 4 || parts.some(part => !/^\d{1,3}$/.test(part) || Number(part) > 255)) return null;
  return parts.reduce((value, part) => (value << 8n) | BigInt(Number(part)), 0n);
}

function parseV6(address: string): bigint | null {
  if (!/^[0-9a-f:]+$/i.test(address) || (address.match(/::/g) ?? []).length > 1) return null;
  const [head, tail] = address.includes("::") ? address.split("::") : [address, undefined];
  const left = head ? head.split(":") : [];
  const right = tail ? tail.split(":") : [];
  const missing = 8 - left.length - right.length;
  if (tail === undefined ? left.length !== 8 : missing < 1) return null;
  const groups = [...left, ...Array(tail === undefined ? 0 : missing).fill("0"), ...right];
  if (groups.some(group => !/^[0-9a-f]{1,4}$/i.test(group))) return null;
  return groups.reduce((value, group) => (value << 16n) | BigInt(parseInt(group, 16)), 0n);
}

/** `10.0.0.0/8`, `2001:db8::/32`, or a bare address (a single host). Host bits are dropped. */
export function parseCidr(entry: string): Network | null {
  const [address, prefixText, extra] = entry.trim().split("/");
  if (extra !== undefined || !address) return null;
  const version = address.includes(":") ? 6 : 4;
  const bits = version === 4 ? 32 : 128;
  const value = version === 4 ? parseV4(address) : parseV6(address);
  const prefix = prefixText === undefined ? bits : /^\d{1,3}$/.test(prefixText) ? Number(prefixText) : NaN;
  if (value === null || !(prefix >= 0 && prefix <= bits)) return null;
  const hostBits = BigInt(bits - prefix);
  return { version, base: (value >> hostBits) << hostBits, prefix };
}

/** True when `inner` lies entirely inside `outer`. */
export function within(inner: Network, outer: Network) {
  if (inner.version !== outer.version || inner.prefix < outer.prefix) return false;
  const shift = BigInt((inner.version === 4 ? 32 : 128) - outer.prefix);
  return (inner.base >> shift) === (outer.base >> shift);
}
