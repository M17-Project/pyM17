// Test vector generator for pyM17.
//
// Prints reference values computed by libm17 as JSON. The Python test suite
// compares pyM17 against them bit for bit, including the Viterbi metrics of
// noisy frames.
//
// Build and run from the repository root, with libm17 checked out next to it:
//   cc -O2 -I../libm17 tools/gen_vectors.c ../libm17/m17.c ../libm17/*/[!u]*.c -o gen_vectors -lm
//   ./gen_vectors > tests/vectors.json

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "m17.h"

extern const uint8_t rand_seq[46];
extern const int8_t symbol_map[4];

static int first;

static void key(const char *k) { printf("%s\n\"%s\": ", first ? "" : ",", k); first = 0; }

static void hex(const uint8_t *b, int n)
{
	putchar('"');
	for (int i = 0; i < n; i++)
		printf("%02x", b[i]);
	putchar('"');
}

static void i8_list(const int8_t *v, int n)
{
	putchar('[');
	for (int i = 0; i < n; i++)
		printf("%s%d", i ? "," : "", v[i]);
	putchar(']');
}

static void f_list(const float *v, int n)
{
	putchar('[');
	for (int i = 0; i < n; i++)
		printf("%s%.9g", i ? "," : "", v[i]);
	putchar(']');
}

// deterministic noise: xorshift32 and the sum of 12 uniform values (Irwin-Hall),
// close to a unit Gaussian. Only additions, so the result is the same on every
// machine. logf(), cosf() and friends are not: glibc picks CPU-specific
// implementations that differ in the last bit.
static uint32_t rng_state = 12345;

static float uniform(void)
{
	rng_state ^= rng_state << 13;
	rng_state ^= rng_state >> 17;
	rng_state ^= rng_state << 5;
	return ((rng_state >> 8) + 0.5f) / 16777216.0f;
}

static float gauss(void)
{
	float sum = -6.0f;
	for (int i = 0; i < 12; i++)
		sum += uniform();
	return sum;
}

static void make_lsf(lsf_t *lsf, const char *src, const char *dst, uint16_t type, uint8_t seed)
{
	uint8_t meta[14];
	for (int i = 0; i < 14; i++)
		meta[i] = (uint8_t)(seed * 17 + i * 29);
	set_LSF(lsf, src, dst, type, meta);
}

int main(void)
{
	printf("{");
	first = 1;

	key("libm17_version");
	printf("\"%s\"", LIBM17_VERSION);

	// ---- callsigns
	static const char *calls[] = {"N0CALL", "SP5WWP", "@ALL", "#M17", "#BLN", "W2FBI-X", "AB1CD/P",
		"sp5wwp", "A", "ABCDEFGHI", "#ABCDEFGH", "K9 Z", "A.B", "1-2/3.4"};
	key("callsigns");
	printf("[");
	for (unsigned i = 0; i < sizeof(calls) / sizeof(calls[0]); i++) {
		uint8_t b[6];
		char dec[10];
		encode_callsign_bytes(b, calls[i]);
		decode_callsign_bytes(dec, b);
		printf("%s{\"text\":\"%s\",\"bytes\":", i ? "," : "", calls[i]);
		hex(b, 6);
		printf(",\"decoded\":\"%s\"}", dec);
	}
	printf("]");

	// ---- CRC
	key("crc");
	printf("[");
	static const char *crc_in[] = {"", "A", "123456789"};
	for (int i = 0; i < 3; i++)
		printf("%s{\"data\":\"%s\",\"crc\":%u}", i ? "," : "", crc_in[i],
			CRC_M17((const uint8_t *)crc_in[i], strlen(crc_in[i])));
	uint8_t ramp[256];
	for (int i = 0; i < 256; i++)
		ramp[i] = (uint8_t)i;
	printf(",{\"hex\":");
	hex(ramp, 256);
	printf(",\"crc\":%u}]", CRC_M17(ramp, 256));

	// ---- tables
	key("golay");
	printf("[");
	for (int d = 0; d < 4096; d++)
		printf("%s%u", d ? "," : "", golay24_encode(d));
	printf("]");

	key("interleaver");
	printf("[");
	for (int i = 0; i < 368; i++)
		printf("%s%u", i ? "," : "", intrl_seq[i]);
	printf("]");

	key("randomizer");
	hex(rand_seq, 46);

	key("rrc_taps_10");
	f_list(rrc_taps_10, 81);
	key("rrc_taps_5");
	f_list(rrc_taps_5, 41);

	// ---- symbol sequences
	int8_t sym[SYM_PER_FRA];
	uint32_t cnt;

	key("preamble_lsf");
	cnt = 0;
	gen_preamble_i8(sym, &cnt, PREAM_LSF);
	i8_list(sym, SYM_PER_FRA);
	key("preamble_bert");
	cnt = 0;
	gen_preamble_i8(sym, &cnt, PREAM_BERT);
	i8_list(sym, SYM_PER_FRA);
	key("eot");
	cnt = 0;
	gen_eot_i8(sym, &cnt);
	i8_list(sym, SYM_PER_FRA);

	// ---- META
	lsf_t lsf;
	make_lsf(&lsf, "SP5WWP", "@ALL", M17_TYPE_STREAM | M17_TYPE_VOICE | M17_TYPE_CAN(5), 1);

	key("meta_position");
	printf("[");
	static const float pos[][7] = {
		// lat, lon, altitude, bearing, speed, radius, validity
		{52.2297f, 21.0122f, 110.5f, 270, 12.5f, 3.0f, 15},
		{-33.8688f, 151.2093f, -20.0f, 0, 0.0f, 1.0f, 8},
		{90.0f, -180.0f, 32267.5f, 511, 2047.5f, 200.0f, 15},
		{-91.0f, 181.0f, -600.0f, 359, 3000.0f, 0.5f, 0},
	};
	for (int i = 0; i < 4; i++) {
		set_LSF_meta_position(&lsf, 1, 2, pos[i][0], pos[i][1], (uint8_t)pos[i][6], pos[i][2],
			(uint16_t)pos[i][3], pos[i][4], pos[i][5]);
		printf("%s{\"lat\":%.9g,\"lon\":%.9g,\"altitude\":%.9g,\"bearing\":%d,\"speed\":%.9g,"
			"\"radius\":%.9g,\"validity\":%d,\"meta\":", i ? "," : "",
			pos[i][0], pos[i][1], pos[i][2], (int)pos[i][3], pos[i][4], pos[i][5], (int)pos[i][6]);
		hex(lsf.meta, 14);
		putchar('}');
	}
	printf("]");

	key("meta_ecd");
	set_LSF_meta_ecd(&lsf, "SP5WWP", "M17-M17");
	hex(lsf.meta, 14);

	key("meta_nonce");
	uint8_t rnd[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
	set_LSF_meta_nonce(&lsf, 1763300000, rnd);
	hex(lsf.meta, 14);

	// ---- frames (clean, int8 symbols)
	key("lsf_frames");
	printf("[");
	static const uint16_t types[] = {
		M17_TYPE_STREAM | M17_TYPE_VOICE | M17_TYPE_CAN(0),
		M17_TYPE_PACKET | M17_TYPE_DATA | M17_TYPE_CAN(10),
		M17_TYPE_STREAM | M17_TYPE_VOICE | M17_TYPE_ENCR_AES | M17_TYPE_ENCR_AES256 | M17_TYPE_SIGNED,
	};
	for (int i = 0; i < 3; i++) {
		make_lsf(&lsf, i ? "N0CALL" : "SP5WWP", i == 1 ? "#M17" : "@ALL", types[i], (uint8_t)i);
		gen_frame_i8(sym, NULL, FRAME_LSF, &lsf, 0, 0);
		printf("%s{\"lsf\":", i ? "," : "");
		hex((uint8_t *)&lsf, 30);
		printf(",\"symbols\":");
		i8_list(sym, SYM_PER_FRA);
		putchar('}');
	}
	printf("]");

	make_lsf(&lsf, "SP5WWP", "@ALL", M17_TYPE_STREAM | M17_TYPE_VOICE | M17_TYPE_CAN(5), 7);
	key("stream_frames");
	printf("[");
	for (int i = 0; i < 8; i++) {
		uint8_t pl[16];
		uint16_t fn = (i == 7) ? (0x8000 | 7) : (uint16_t)(i * 4097 % 0x8000);
		for (int k = 0; k < 16; k++)
			pl[k] = (uint8_t)(i * 31 + k * 7);
		gen_frame_i8(sym, pl, FRAME_STR, &lsf, (uint8_t)(i % 6), fn);
		printf("%s{\"lsf\":", i ? "," : "");
		hex((uint8_t *)&lsf, 30);
		printf(",\"lich_cnt\":%d,\"fn\":%u,\"payload\":", i % 6, fn);
		hex(pl, 16);
		printf(",\"symbols\":");
		i8_list(sym, SYM_PER_FRA);
		putchar('}');
	}
	printf("]");

	key("packet_frames");
	printf("[");
	for (int i = 0; i < 4; i++) {
		uint8_t chunk[26];
		for (int k = 0; k < 25; k++)
			chunk[k] = (uint8_t)(i * 13 + k * 11);
		chunk[25] = (i == 3) ? (uint8_t)((1 << 7) | (17 << 2)) : (uint8_t)(i << 2);
		gen_frame_i8(sym, chunk, FRAME_PKT, NULL, 0, 0);
		printf("%s{\"chunk\":", i ? "," : "");
		hex(chunk, 26);
		printf(",\"symbols\":");
		i8_list(sym, SYM_PER_FRA);
		putchar('}');
	}
	printf("]");

	key("bert_frame");
	{
		uint8_t bert[25];
		for (int k = 0; k < 25; k++)
			bert[k] = (uint8_t)(0xA5 ^ (k * 37));
		bert[24] &= 0x80; // 197 bits
		gen_frame_i8(sym, bert, FRAME_BERT, NULL, 0, 0);
		printf("{\"data\":");
		hex(bert, 25);
		printf(",\"symbols\":");
		i8_list(sym, SYM_PER_FRA);
		putchar('}');
	}

	// ---- noisy frames with libm17's decode results
	key("noisy");
	printf("[");
	int n_out = 0;
	static const float sigmas[] = {0.3f, 0.6f, 0.9f};
	for (int s = 0; s < 3; s++) {
		for (int kind = 0; kind < 3; kind++) {
			for (int rep = 0; rep < 3; rep++) {
				float f[SYM_PER_FRA];
				uint8_t chunk[26], pl[16];
				uint16_t fn = (uint16_t)(rep * 1234 + s);
				uint8_t lich_cnt = (uint8_t)((rep + s) % 6);
				make_lsf(&lsf, "SP5WWP", "@ALL", M17_TYPE_STREAM | M17_TYPE_VOICE, (uint8_t)(rep + s));
				for (int k = 0; k < 16; k++)
					pl[k] = (uint8_t)(rep * 7 + k * 13 + s);
				for (int k = 0; k < 25; k++)
					chunk[k] = (uint8_t)(rep * 5 + k * 3 + s);
				chunk[25] = (uint8_t)((rep & 1) ? ((1 << 7) | (9 << 2)) : (rep << 2));

				if (kind == 0)
					gen_frame_i8(sym, NULL, FRAME_LSF, &lsf, 0, 0);
				else if (kind == 1)
					gen_frame_i8(sym, pl, FRAME_STR, &lsf, lich_cnt, fn);
				else
					gen_frame_i8(sym, chunk, FRAME_PKT, NULL, 0, 0);
				for (int k = 0; k < SYM_PER_FRA; k++)
					f[k] = (float)sym[k] + sigmas[s] * gauss();

				printf("%s{\"kind\":\"%s\",\"symbols\":", n_out++ ? "," : "",
					kind == 0 ? "lsf" : kind == 1 ? "stream" : "packet");
				f_list(&f[SYM_PER_SWD], SYM_PER_PLD);
				if (kind == 0) {
					lsf_t out;
					uint32_t e = decode_LSF(&out, &f[SYM_PER_SWD]);
					printf(",\"lsf\":");
					hex((uint8_t *)&out, 30);
					printf(",\"metric\":%u}", e);
				} else if (kind == 1) {
					uint8_t data[16], lich[5], lc;
					uint16_t fno;
					uint32_t e = decode_str_frame(data, lich, &fno, &lc, &f[SYM_PER_SWD]);
					printf(",\"payload\":");
					hex(data, 16);
					printf(",\"fn\":%u,\"lich\":", fno);
					hex(lich, 5);
					printf(",\"lich_cnt\":%u,\"metric\":%u}", lc, e);
				} else {
					uint8_t data[25], eof, fno;
					uint32_t e = decode_pkt_frame(data, &eof, &fno, &f[SYM_PER_SWD]);
					printf(",\"data\":");
					hex(data, 25);
					printf(",\"eof\":%u,\"counter\":%u,\"metric\":%u}", eof, fno, e);
				}
			}
		}
	}
	printf("]");

	printf("\n}\n");
	return 0;
}
