import { describe, expect, it } from "vitest";
import { parseCidr, within } from "./cidr";

const net = (text: string) => parseCidr(text)!;

describe("parseCidr", () => {
  it("parses an IPv4 network and drops host bits", () => expect(parseCidr("10.1.2.3/8")).toEqual({ version: 4, base: BigInt(10) << 24n, prefix: 8 }));
  it("treats a bare IPv4 address as a single host", () => expect(parseCidr(" 192.168.0.1 ")).toEqual({ version: 4, base: (192n << 24n) | (168n << 16n) | 1n, prefix: 32 }));
  it("accepts the extremes /0 and /32", () => {
    expect(parseCidr("0.0.0.0/0")).toEqual({ version: 4, base: 0n, prefix: 0 });
    expect(parseCidr("255.255.255.255/32")!.base).toBe(0xffffffffn);
  });
  it.each(["10.0.0.0/33", "10.0.0.0/-1", "10.0.0.0/x", "10.0.0.0/", "10.0.0.0/8/8", "256.0.0.1", "1.2.3", "1.2.3.4.5", "1.2.3.a", "01234.1.1.1", "", "/8", " "])("refuses the IPv4 entry %j", (entry) => expect(parseCidr(entry)).toBeNull());
  it("parses IPv6 networks, the compressed and the full form", () => {
    expect(parseCidr("2001:db8::/32")).toEqual({ version: 6, base: 0x20010db8n << 96n, prefix: 32 });
    expect(parseCidr("2001:db8:0:0:0:0:0:1")).toMatchObject({ version: 6, prefix: 128, base: (0x20010db8n << 96n) | 1n });
    expect(parseCidr("::1")).toMatchObject({ version: 6, base: 1n, prefix: 128 });
    expect(parseCidr("::/0")).toEqual({ version: 6, base: 0n, prefix: 0 });
  });
  it.each(["2001:db8::/129", "2001::db8::1", "2001:db8:0:0:0:0:0", "1:2:3:4:5:6:7:8:9", "gggg::1", "2001:db8::12345", "1:2:3:4:5:6:7::8", "::ffff:1.2.3.4"])("refuses the IPv6 entry %j", (entry) => expect(parseCidr(entry)).toBeNull());
  it("accepts an IPv6 prefix of 128 and 0", () => {
    expect(parseCidr("::1/128")!.prefix).toBe(128);
    expect(parseCidr("::1/0")!.base).toBe(0n);
  });
});

describe("within", () => {
  it("is true for a network inside a wider one and for an identical one", () => {
    expect(within(net("10.1.2.0/24"), net("10.0.0.0/8"))).toBe(true);
    expect(within(net("10.0.0.0/8"), net("10.0.0.0/8"))).toBe(true);
    expect(within(net("10.9.9.9"), net("10.0.0.0/8"))).toBe(true);
    expect(within(net("2001:db8:1::/48"), net("2001:db8::/32"))).toBe(true);
  });
  it("is false for a wider network, a different network or a different version", () => {
    expect(within(net("10.0.0.0/8"), net("10.1.0.0/16"))).toBe(false);
    expect(within(net("11.0.0.1"), net("10.0.0.0/8"))).toBe(false);
    expect(within(net("::1"), net("0.0.0.0/0"))).toBe(false);
    expect(within(net("10.0.0.1"), net("::/0"))).toBe(false);
  });
  it("treats /0 as containing everything of the same version", () => {
    expect(within(net("203.0.113.5"), net("0.0.0.0/0"))).toBe(true);
    expect(within(net("2001:db8::1"), net("::/0"))).toBe(true);
  });
  it("is exact at the prefix boundary", () => {
    expect(within(net("10.0.0.255"), net("10.0.0.0/24"))).toBe(true);
    expect(within(net("10.0.1.0"), net("10.0.0.0/24"))).toBe(false);
  });
});
