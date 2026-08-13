/* Deterministic, greppable UART report protocol for AST2050 firmware tests.
 *
 * The SAME binary runs on QEMU and (later) on real silicon; the integration
 * harness (integration/) diffs the two transcripts byte-for-byte after
 * normalisation, so the output MUST be deterministic (no timestamps, no
 * addresses that vary by build). Line grammar:
 *
 *   [FWT] begin <name>
 *   [FWT] reg <label> <addr:08x> = <val:08x>
 *   [FWT] kv <key> = <val:08x>
 *   [FWT] check <label> <PASS|FAIL> got=<08x> want=<08x>
 *   [FWT] end <name> checks=<n> fails=<n>
 *   [FWT] halt
 *
 * Apache-2.0.
 */
#ifndef CONSOLE_H
#define CONSOLE_H

#include "ast2050.h"

void console_init(void);
void con_putc(char c);
void con_puts(const char *s);
void con_puthex32(u32 v);

/* Report protocol helpers (keep static pass/fail counters). */
void fwt_begin(const char *name);
u32  fwt_reg(const char *label, u32 addr);   /* prints + returns the value */
void fwt_kv(const char *key, u32 val);
void fwt_check(const char *label, u32 got, u32 want);
void fwt_end(const char *name);

#endif /* CONSOLE_H */
