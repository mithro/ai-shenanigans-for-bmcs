/* Entry after crt0: init console, run the linked peripheral test, report.
 * Apache-2.0. */
#include "harness.h"

void fwtest_main(void)
{
    console_init();
    fwt_begin(fwtest_name);
    fwtest_run();
    fwt_end(fwtest_name);
}
