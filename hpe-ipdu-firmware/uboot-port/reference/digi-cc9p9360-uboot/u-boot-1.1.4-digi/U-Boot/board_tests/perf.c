/*
 *  board_tests/perf.c
 *
 *  Copyright (C) 2006 by Digi International Inc.
 *  All rights reserved.
 *
 *  This program is free software; you can redistribute it and/or modify it
 *  under the terms of the GNU General Public License version2  as published by
 *  the Free Software Foundation.
*/
/*
 *  !Revision:   $Revision$: 
 *  !Author:     Markus Pietrek
 *  !Descr:      Performs some performance tests
*/

#include "common.h"

/* ********** defines ********** */

#define MEM_TEST_LOOP   1
#define MEM_TEST_SIZE 	MiB(1)

#if MEM_TEST_SIZE > BOARD_TEST_SDRAM_SIZE
# error need more test memory on board
#endif

#define INC_COUNTER	2000000
#define MAX_TIMERS 	3

#define CLOCK_GET() 	get_timer(0)
#define CLOCK_RATE()	iClocksPerSec   /* u-boot measures in ms */

#ifdef CONFIG_UNC90
/* uses a 32.768 kHz counter with a reload of 1000, thus a measurable range
   from 30us to 30ms. As we have no interrupts, we need to poll the timer
   often. */
# define POLL_COUNTER() \
        { \
                static int _iCounter = 0; \
                if( !( _iCounter++ % 512 ) )  \
                            CLOCK_GET(); \
        }
#else
# define POLL_COUNTER() do { } while( 0 )
#endif

/* ********** typedefs ********** */

typedef void (*WorkFunc_t) (void);

/* ********** local function declarations ********** */

static void DoTests( void );

static void MemRead8( void );
static void MemRead16( void );
static void MemRead32( void );
static void CpuInc( void );

static void PerfTest( WorkFunc_t pfFunc, const char* szLabel );
static void TimerStart( int iTimerIdx, const char* szLabel  );
static double TimerStop(  int iTimerIdx );


/* ********** local variable definitions ********** */

static clock_t aTimerStart[ MAX_TIMERS ];
static int     iClocksPerSec = 0;

int main( int argc, char* argv[] )
{
        clock_t start;
        clock_t stop;
        
        printf( "perf: $Revision$, compiled on %s at %s\n", __DATE__, __TIME__ );

        printf( "Calibrating Timer: " );
        start = CLOCK_GET();
        udelay( 100000 );       /* 100ms */
        stop  = CLOCK_GET();
        iClocksPerSec = 10 * ( stop - start ); /* normalize it to 1s */
        printf( "%i Clocks/Sec\n", iClocksPerSec );

#ifdef CONFIG_UNC90
        printf( "!!! Timer is frequently polled, so don't use UNC90 results in absolute performance comparisions to other platforms. Relative (to itself) is ok\n" );
#endif                          /* CONFIG_UNC90 */


        if( run_command( "dcache off; icache off", 0 ) != 1 )
                ERROR( "Unknown cache status\n" );
        DoTests();

        if( run_command( "dcache off; icache on", 0 ) != 1 )
                ERROR( "Failed\n" );
        DoTests();

        if( run_command( "dcache on; icache off", 0 ) != 1 )
                ERROR( "Failed\n" );
        DoTests();
        
        if( run_command( "dcache on; icache on", 0 ) != 1 )
                ERROR( "Failed\n" );
        DoTests();
        
        return EXIT_SUCCESS;
}

/* ********** local function implementations ********** */

static void DoTests( void )
{
        printf( "CPU\n" );
        PerfTest( CpuInc,    "  Increment" );

        printf( "\nMemory Read (%i KiB)\n",
                ( MEM_TEST_LOOP * MEM_TEST_SIZE ) / 1024 );

        PerfTest( MemRead8,  "   8bit" );
        PerfTest( MemRead16, "  16bit" );
        PerfTest( MemRead32, "  32bit" );
}

static void MemRead8( void )
{
        int i;
        volatile unsigned char ucTmp;
        for( i = 0; i < MEM_TEST_LOOP; i++ ) {
                const volatile unsigned char* pucTest = (const volatile unsigned char*) BOARD_TEST_SDRAM_START;
                const volatile unsigned char* pucEnd  = pucTest + 
                        ( MEM_TEST_SIZE / sizeof( unsigned char ) );

                
                while( pucTest != pucEnd ) {
                        POLL_COUNTER();
                        ucTmp = *pucTest;
                        pucTest++;
                }
        }
}

static void MemRead16( void )
{
        int i;
        volatile unsigned short uhTmp;

        for( i = 0; i < MEM_TEST_LOOP; i++ ) {
                const volatile unsigned short* puhTest = (const volatile unsigned short*) BOARD_TEST_SDRAM_START;
                const volatile unsigned short* puhEnd  = puhTest + 
                        ( MEM_TEST_SIZE / sizeof( unsigned short ) );
                
                while( puhTest != puhEnd ) {
                        POLL_COUNTER();
                        uhTmp = *puhTest;
                        puhTest++;
                }
        }
}

static void MemRead32( void )
{
        int i;
        volatile unsigned short uiTmp;

        for( i = 0; i < MEM_TEST_LOOP; i++ ) {
                const volatile unsigned int* puiTest = (const volatile unsigned int*) BOARD_TEST_SDRAM_START;
                const volatile unsigned int* puiEnd  = puiTest + 
                        ( MEM_TEST_SIZE / sizeof( unsigned int ) );
                
                while( puiTest != puiEnd ) {
                        POLL_COUNTER();
                        uiTmp = *puiTest;
                        puiTest++;
                }
        }
}

static void CpuInc( void )
{
        volatile register unsigned int uiTmp = 0;
        int i;
        
        for( i = 0; i < INC_COUNTER; i++ ) {
                POLL_COUNTER();
                uiTmp++;
        }
}

/***********************************************************************
 * !Function: PerfTest
 * !Return:   nothing
 ***********************************************************************/

static void PerfTest( WorkFunc_t pfWork, const char* szLabel )
{
	TimerStart( 0, szLabel );
        pfWork();
        TimerStop( 0 );
}

/***********************************************************************
 * !Function: TimerStart
 * !Descr:    notes the current system time in clock ticks.
 ***********************************************************************/

static void TimerStart( int iTimerIdx, const char* szLabel )
{
        printf( "%s: ", szLabel );
	aTimerStart[ iTimerIdx ] = CLOCK_GET();
}


/***********************************************************************
 * !Function: TimerStop
 * !Return:   time in ms
 * !Descr:    prints the elapsed time since perfElapseTimeStart
 ***********************************************************************/

static double TimerStop( int iTimerIdx )
{
	clock_t timeStop = CLOCK_GET();
        clock_t timeDiff;
	double  dTimeDiffMiliSeconds;

	timeDiff = timeStop - aTimerStart[ iTimerIdx ];
        dTimeDiffMiliSeconds = (((double) timeDiff)*1000)/CLOCK_RATE();

        printf( "%6i ms\n", (int) dTimeDiffMiliSeconds );

	return dTimeDiffMiliSeconds;
}
