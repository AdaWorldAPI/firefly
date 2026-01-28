/**
 * LadybugDB Hamming Operations - TypeScript
 * Same XOR + POPCOUNT as Python, Rust, Go, C...
 */

const DIM = 10_000;
const DIM_U64 = 157;
const LAST_MASK = BigInt((1 << 16) - 1);

export class HammingVector {
  data: BigUint64Array;

  constructor(data?: BigUint64Array) {
    this.data = data ?? new BigUint64Array(DIM_U64);
  }

  static async fromSeed(seed: string): Promise<HammingVector> {
    const data = new BigUint64Array(DIM_U64);
    const encoder = new TextEncoder();
    
    for (let i = 0; i < DIM_U64; i++) {
      const input = encoder.encode(`${seed}:${i}`);
      const hashBuffer = await crypto.subtle.digest('SHA-256', input);
      const view = new DataView(hashBuffer);
      data[i] = view.getBigUint64(0, true);
    }
    data[DIM_U64 - 1] &= LAST_MASK;
    return new HammingVector(data);
  }

  xor(other: HammingVector): HammingVector {
    const result = new BigUint64Array(DIM_U64);
    for (let i = 0; i < DIM_U64; i++) {
      result[i] = this.data[i] ^ other.data[i];
    }
    result[DIM_U64 - 1] &= LAST_MASK;
    return new HammingVector(result);
  }

  hamming(other: HammingVector): number {
    let total = 0;
    for (let i = 0; i < DIM_U64; i++) {
      let x = this.data[i] ^ other.data[i];
      while (x > 0n) {
        total += Number(x & 1n);
        x >>= 1n;
      }
    }
    return total;
  }

  similarity(other: HammingVector): number {
    return 1.0 - this.hamming(other) / DIM;
  }

  toHex(): string {
    const bytes = new Uint8Array(this.data.buffer);
    return Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('');
  }

  static fromHex(hex: string): HammingVector {
    const bytes = new Uint8Array(hex.match(/.{2}/g)!.map(b => parseInt(b, 16)));
    return new HammingVector(new BigUint64Array(bytes.buffer));
  }
}

export async function fingerprint(name: string, signature: string, body: string): Promise<HammingVector> {
  return HammingVector.fromSeed(`${name}::${signature}::${body}`);
}

export function resonate(
  query: HammingVector, 
  corpus: HammingVector[], 
  threshold: number = 0.5
): Array<[number, number]> {
  const results: Array<[number, number]> = [];
  for (let i = 0; i < corpus.length; i++) {
    const sim = query.similarity(corpus[i]);
    if (sim >= threshold) {
      results.push([i, sim]);
    }
  }
  results.sort((a, b) => b[1] - a[1]);
  return results;
}