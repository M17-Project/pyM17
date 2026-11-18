// Encryption and signature test vectors for pyM17, from gr-m17's code:
// tinier-aes (AES-CTR), micro-ecc (ECDSA), gr-m17's stream hash (lib/m17sig.c on sha-2, M17
// specification 2.1) and gr-m17's scrambler generator.
//
// Build and run from the repository root, with gr-m17 (1.1.0 or later, submodules included)
// checked out next to it:
//   G=../gr-m17
//   cc -O2 -ffp-contract=off -I$G/tinier-aes -I$G/micro-ecc -I$G/lib -I$G/sha-2 tools/gen_crypto_vectors.c \
//     $G/tinier-aes/aes.c $G/micro-ecc/uECC.c $G/lib/m17sig.c $G/sha-2/sha-256.c -o gen_crypto_vectors
//   ./gen_crypto_vectors > tests/crypto_vectors.json

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "aes.h"
#include "uECC.h"
#include "m17sig.h"

static void hex(const uint8_t *b, int n)
{
	putchar('"');
	for (int i = 0; i < n; i++)
		printf("%02x", b[i]);
	putchar('"');
}

// gr-m17 m17_coder_impl::scrambler_sequence_generator(), one frame
static uint32_t scrambler_frame(uint32_t seed, int subtype, uint8_t out[16])
{
	uint32_t lfsr = seed, bit;
	uint8_t pn[128];
	for (int i = 0; i < 128; i++) {
		if (subtype == 0)
			bit = (lfsr >> 7) ^ (lfsr >> 5) ^ (lfsr >> 4) ^ (lfsr >> 3);
		else if (subtype == 1)
			bit = (lfsr >> 15) ^ (lfsr >> 14) ^ (lfsr >> 12) ^ (lfsr >> 3);
		else
			bit = (lfsr >> 23) ^ (lfsr >> 22) ^ (lfsr >> 21) ^ (lfsr >> 16);
		bit &= 1;
		lfsr = ((lfsr << 1) | bit) & 0xFFFFFF;
		pn[i] = (uint8_t)bit;
	}
	pack_bit_array_into_byte_array(pn, out, 16);
	return lfsr & (subtype == 0 ? 0xFF : subtype == 1 ? 0xFFFF : 0xFFFFFF);
}

// deterministic RNG for micro-ecc, so the vectors are reproducible
static uint32_t rng_state = 0x1234567;
static int rng(uint8_t *dest, unsigned size)
{
	for (unsigned i = 0; i < size; i++) {
		rng_state = rng_state * 1103515245u + 12345u;
		dest[i] = (uint8_t)(rng_state >> 16);
	}
	return 1;
}

int main(void)
{
	printf("{\n\"aes\": [");
	uint8_t key[32], nonce[14];
	for (int i = 0; i < 32; i++)
		key[i] = (uint8_t)(i * 7 + 1);
	for (int i = 0; i < 14; i++)
		nonce[i] = (uint8_t)(0xA0 + i);
	int n = 0;
	for (int type = 0; type < 3; type++) {
		static const uint16_t fns[] = {0, 1, 255, 0x7FFF, 0x8005};
		for (int k = 0; k < 5; k++) {
			uint8_t iv[16], pl[16], ct[16];
			memcpy(iv, nonce, 14);
			iv[14] = (uint8_t)((fns[k] >> 8) & 0x7F); // as gr-m17: EOS bit cleared
			iv[15] = (uint8_t)(fns[k] & 0xFF);
			for (int i = 0; i < 16; i++)
				pl[i] = (uint8_t)(k * 16 + i);
			memcpy(ct, pl, 16);
			aes_ctr_bytewise_payload_crypt(iv, key, ct, type);
			printf("%s{\"key\":", n++ ? "," : "");
			hex(key, 16 + 8 * type);
			printf(",\"nonce\":");
			hex(nonce, 14);
			printf(",\"fn\":%u,\"plain\":", fns[k]);
			hex(pl, 16);
			printf(",\"cipher\":");
			hex(ct, 16);
			putchar('}');
		}
	}
	printf("],\n\"scrambler\": [");
	static const uint32_t seeds[] = {0xA5, 0x1234, 0xABCDEF};
	for (int type = 0; type < 3; type++) {
		uint32_t s = seeds[type];
		printf("%s{\"seed\":", type ? "," : "");
		uint8_t sb[3] = {(uint8_t)(s >> 16), (uint8_t)(s >> 8), (uint8_t)s};
		hex(&sb[2 - type], type + 1);
		printf(",\"keystream\":[");
		for (int f = 0; f < 4; f++) {
			uint8_t ks[16];
			s = scrambler_frame(s, type, ks);
			printf("%s", f ? "," : "");
			hex(ks, 16);
		}
		printf("]}");
	}

	printf("],\n\"ecdsa\": ");
	uECC_set_rng(rng);
	const struct uECC_Curve_t *curve = uECC_secp256r1();
	uint8_t priv[32], pub[64], pub2[64], hash[32], sig[64], pl[16], auth[16];
	uECC_make_key(pub, priv, curve);
	uECC_compute_public_key(priv, pub2, curve);
	// gr-m17's stream hash: 5 frames (FN 0..4), then the Authentication Frame N0CALL -> W1AW
	static const uint8_t n0call[6] = {0x00, 0x00, 0x4b, 0x13, 0xd1, 0x06};
	static const uint8_t w1aw[6] = {0x00, 0x00, 0x00, 0x16, 0x80, 0xb7};
	const uint32_t ts = 217123200; // 2026-11-18T00:00:00Z, seconds since 2020-01-01
	m17sig_ctx_t ctx;
	m17sig_init(&ctx);
	for (int f = 0; f < 5; f++) {
		for (int i = 0; i < 16; i++)
			pl[i] = (uint8_t)(f * 9 + i * 3);
		m17sig_frame(&ctx, (uint16_t)f, pl);
	}
	m17sig_auth_build(auth, n0call, w1aw, ts);
	m17sig_frame(&ctx, M17SIG_FN_AUTH, auth);
	m17sig_final(&ctx, hash);
	uECC_sign(priv, hash, 32, sig, curve);
	printf("{\"private\":");
	hex(priv, 32);
	printf(",\"public\":");
	hex(pub2, 64);
	printf(",\"signer\":\"N0CALL\",\"destination\":\"W1AW\",\"timestamp\":%u", (unsigned)(ts + M17SIG_EPOCH));
	printf(",\"auth\":");
	hex(auth, 16);
	printf(",\"hash\":");
	hex(hash, 32);
	printf(",\"signature\":");
	hex(sig, 64);
	printf(",\"verifies\":%d}\n}\n", uECC_verify(pub, hash, 32, sig, curve));
	return 0;
}
