/* Contract each peripheral test implements. See fwtest/README or ../README.md.
 * Apache-2.0. */
#ifndef HARNESS_H
#define HARNESS_H

#include "console.h"

/* Each peripherals/<p>/fwtest.c provides these two symbols. */
extern const char fwtest_name[];
void fwtest_run(void);

/* Provided by crt0.S -> main.c. */
void fwtest_main(void);

#endif /* HARNESS_H */
