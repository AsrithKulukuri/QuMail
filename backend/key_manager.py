"""Fast protocol-level BB84 simulator for the QuMail demo.

This is a software simulation of BB84, not physical QKD hardware. It models:
1) random raw bits and bases, 2) quantum-basis measurement behaviour,
3) optional intercept-resend Eve, 4) basis sifting, and 5) QBER sampling.
"""
import random
from dataclasses import dataclass

@dataclass
class BB84Result:
    key_bytes: bytes
    sifted_bits: list[int]
    total_transmissions: int
    matching_bases: int
    qber: float
    eve_probability: float
    accepted: bool


def _measure(bit: int, alice_basis: int, bob_basis: int, eve_probability: float) -> int:
    # 0 = Z basis, 1 = X basis. Wrong-basis measurement is intrinsically random.
    if random.random() < eve_probability:
        eve_basis = random.getrandbits(1)
        eve_bit = bit if eve_basis == alice_basis else random.getrandbits(1)
        return eve_bit if bob_basis == eve_basis else random.getrandbits(1)
    return bit if bob_basis == alice_basis else random.getrandbits(1)


def _bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        chunk = bits[i:i+8]
        if len(chunk) < 8:
            break
        value = 0
        for b in chunk:
            value = (value << 1) | b
        out.append(value)
    return bytes(out)


def generate_bb84_key(key_bits: int = 4096, eve_probability: float = 0.0,
                      qber_threshold: float = 0.11) -> BB84Result:
    if key_bits < 128 or key_bits % 8:
        raise ValueError('key_bits must be a multiple of 8 and at least 128')
    if not 0 <= eve_probability <= 1:
        raise ValueError('eve_probability must be between 0 and 1')

    # ~50% basis matches; 4x oversampling gives comfortable headroom after sampling.
    transmissions = max(1024, key_bits * 4)
    alice_bits = [random.getrandbits(1) for _ in range(transmissions)]
    alice_bases = [random.getrandbits(1) for _ in range(transmissions)]
    bob_bases = [random.getrandbits(1) for _ in range(transmissions)]
    bob_bits = [_measure(a, ab, bb, eve_probability)
                for a, ab, bb in zip(alice_bits, alice_bases, bob_bases)]

    sifted_a, sifted_b = [], []
    for a, b, ab, bb in zip(alice_bits, bob_bits, alice_bases, bob_bases):
        if ab == bb:
            sifted_a.append(a); sifted_b.append(b)

    matching = len(sifted_a)
    sample_size = min(max(32, matching // 10), matching)
    errors = sum(a != b for a, b in zip(sifted_a[:sample_size], sifted_b[:sample_size]))
    qber = errors / sample_size if sample_size else 1.0
    usable = sifted_a[sample_size:]
    accepted = qber <= qber_threshold and len(usable) >= key_bits
    if not accepted:
        return BB84Result(b'', usable, transmissions, matching, qber, eve_probability, False)
    bits = usable[:key_bits]
    return BB84Result(_bits_to_bytes(bits), bits, transmissions, matching,
                      qber, eve_probability, True)
