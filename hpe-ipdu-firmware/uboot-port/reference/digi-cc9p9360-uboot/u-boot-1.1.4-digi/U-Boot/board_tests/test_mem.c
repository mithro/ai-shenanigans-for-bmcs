/*
 *  board_tests/test_mem.c
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
 *  !Descr:      Performs some memory tests
 *  !References: [1] examples/test_burst.c
*/

#include "common.h"

#define PRINTF( ... ) \
        do {          \
                if( !lcSilent ) \
                        printf( __VA_ARGS__ );  \
        } while( 0 )            \
        
#define MEM( TYPE ) \
	{ .szName  = #TYPE, \
          .pucMem = (uchar*) BOARD_TEST_ ## TYPE ## _START, \
          .iSize   = BOARD_TEST_ ## TYPE ## _SIZE }

#define CLEAR_SDRAM_DST()                                               \
        memset( laxMem[ SDRAM_DST ].pucMem, 0, laxMem[ SDRAM_DST ].iSize )

typedef void(*CopyBurstFunc_t) ( const uchar* pucSrc, uchar* pucDst );
typedef int(*CmdLineFuncHandler_t)( void );

typedef struct {
        const char*          szName;
        char                 cDoInAll;
        CmdLineFuncHandler_t pfFunc;
} CmdLineFunc_t;

typedef struct 
{
        const char* szName;
        uchar*      pucMem;
        ssize_t     iSize;
} MemInfo_t;

/* corresponds to MemInfo */
typedef enum {
        SDRAM_SRC  = 0,
        SDRAM_DST  = 1,
        NOR        = 2,
} MemInfoType_t;

typedef enum {
        FT_00,
        FT_FF,
        FT_INC,
        FT_NONE
} FillTypes_t;

/* ********** local function declarations ********** */

static int  RunFunction( const char* szFunc );
static void ProcessedOneArg( void );

static int Usage( void );
static int OptSilent( void );
static int OptEndless( void );
static int OptPatternSize( void );
static int SetPatternSize( int iPatternSize );
static int TestAll( void );
static int TestBurstSDRAM( void );
static int TestWriteNOR( void );
static int TestBurstNOR( void );
static int TestBurstCopyNOR( void );
static int TestBurstCopyNOR2048( void );

static void CopyBurst( MemInfoType_t eSrc, MemInfoType_t eDst,
                       size_t iBurstSize );
static void CopyBurstBlock( uchar* pucSrc, uchar* pucDst,
                            size_t iBurstSize, size_t iCopySize );
static int  CopyToFlash( void );

static void PatternFill1( FillTypes_t eFillType, size_t iSize );
static int  PatternVerify1( MemInfoType_t eMemType, FillTypes_t eFillType );
static void UpdateVal1( FillTypes_t eFillType, /*@inout@*/ unsigned char* pucVal );
static void PatternFill2( FillTypes_t eFillType, size_t iSize );
static int  PatternVerify2( MemInfoType_t eMemType, FillTypes_t eFillType );
static void UpdateVal2( FillTypes_t eFillType, /*@inout@*/ unsigned short* puhVal );
static void PatternFill4( FillTypes_t eFillType, size_t iSize );
static int  PatternVerify4( MemInfoType_t eMemType, FillTypes_t eFillType );
static void UpdateVal4( FillTypes_t eFillType, /*@inout@*/ unsigned int* puiVal );

/* Tries to copy 1 Bytes in one access */
static inline void MemCpyBurst1(  const uchar* pucSrc, uchar* pucDst ) 
{
        *pucDst = *pucSrc;
}

/* Tries to copy 2 Bytes in one access */
static inline void MemCpyBurst2(  const uchar* pucSrc, uchar* pucDst ) 
{
        *(unsigned short*) pucDst = *(unsigned short*) pucSrc;
}

/* Tries to copy 4 Bytes in one access */
static inline void MemCpyBurst4(  const uchar* pucSrc, uchar* pucDst ) 
{
        *(unsigned int*) pucDst = *(unsigned int*) pucSrc;
}

/* Tries to copy 8 Bytes in one access */
static inline void MemCpyBurst8(  const uchar* pucSrc, uchar* pucDst )
{
        __asm__ __volatile__ (
	     "ldmia %0,{r4-r5}\n"
	     "stmia %1,{r4-r5}\n"
             :
             : "r"(pucSrc),"r"(pucDst)
             : "r4","r5" );
}

static inline void MemCpyBurst16( const uchar* pucSrc, uchar* pucDst )
{
        __asm__ __volatile__ (
	     "ldmia %0,{r4-r7}\n"
	     "stmia %1,{r4-r7}\n"
             :
             : "r"(pucSrc),"r"(pucDst)
             : "r4","r5","r6","r7" );
}

static inline void MemCpyBurst32( const uchar* pucSrc, uchar* pucDst )
{
        /* r8 is reserved by U-Boot */
        __asm__ __volatile__ (
	     "ldmia %0,{r2-r7,r9-r10}\n"
	     "stmia %1,{r2-r7,r9-r10}\n"
             :
             : "r"(pucSrc),"r"(pucDst)
             : "r2","r3","r4","r5","r6","r7","r9","r10" );
}

static void (*PatternFill)( FillTypes_t eFillType, size_t iSize ) = NULL;
static int  (*PatternVerify)( MemInfoType_t eMemType, FillTypes_t eFillType ) = NULL;

/* ********** local variable definitions ********** */

static CmdLineFunc_t laxCmdLineFunctions[] = {
        { "--help",         0, Usage },
        { "--pattern_size", 0, OptPatternSize },
        { "--silent",       0, OptSilent },
        { "--endless",      0, OptEndless },
        { "all",            0, TestAll },
        { "burst_sdram",    1, TestBurstSDRAM },
        { "write_nor",      1, TestWriteNOR },
        { "burst_nor",      1, TestBurstNOR },
        { "burst_copy_nor", 1, TestBurstCopyNOR },
        { "burst_copy_nor2048", 1, TestBurstCopyNOR2048 },
};

/* unprocessed command line arguments */
static int    largc = 0;
static char** largv = NULL;
static char   lcSilent  = 0;
static char   lcEndless = 0;

/* define BOARD_TEST in include/configs/<board>.h */
static const MemInfo_t laxMem[] = {
	{ .szName  = "SDRAM Lower Half", \
          .pucMem = (uchar*) BOARD_TEST_SDRAM_START, \
          .iSize   = BOARD_TEST_SDRAM_SIZE / 2 },
	{ .szName  = "SDRAM Upper Half", \
          .pucMem = (uchar*) BOARD_TEST_SDRAM_START + BOARD_TEST_SDRAM_SIZE / 2, \
          .iSize   = BOARD_TEST_SDRAM_SIZE / 2 },
        MEM( NOR )
};

static const char* aszFillTypes[ FT_NONE ] = {
        " zeroes",
        " 0xff",
        " incremental"
};
        

/* ********** function implementations ********** */
        
int main( int argc, char* argv[] )
{
        int i;
        int iLoop = 0;
        
        printf( "test_mem: $Revision$, compiled on %s at %s\n",
        	__DATE__, __TIME__ );

        if( XF_VERSION != get_version() ) {
                ERROR( "Expect U-Boot ABI Version %i, have %i\n",
                        XF_VERSION, get_version() );
                return EXIT_FAILURE;
        }

        if( argc < 1 ) {
                ERROR( "Expect at least start address from U-Boot\n" );
                return EXIT_FAILURE;
        }

        /* get rid of address in commandline */
        argc--;
        memcpy( &argv[ 0 ], &argv[ 1 ], argc * sizeof( argv[ 0 ] ) );

        printf( "Using Built-In Memory Areas:\n" );
        for( i = 0; i < ARRAY_SIZE( laxMem ); i++ )
                printf( "    %s @ 0x%08x (0x%08x)\n",
                        laxMem[ i ].szName, laxMem[ i ].pucMem,
                        laxMem[ i ].iSize );

        if( laxMem[ SDRAM_SRC ].iSize != laxMem[ SDRAM_DST ].iSize )
        	ERROR( "Memory Sizes mismatch\n" );

        printf( "\n" );

        do {
                largc = argc;
                largv = argv;
                SetPatternSize( 1 );

                if( !largc )
                        TestAll();
                else {
                        /* process all arguments */
                        while( largc ) {
                                if( !RunFunction( largv[ 0 ] ) )
                                        return EXIT_FAILURE;
                                ProcessedOneArg();
                        }
                }
                iLoop++;
                printf( "** Loop %i\n", iLoop );
        } while( !lcEndless );

        printf( "** Tests passed\n" );
        
        return EXIT_SUCCESS;
}

/***********************************************************************
 * !Function: RunFunction
 * !Return:   0 on failure otherwise 1
 * !Descr:    Runs the function szFunc if available
 ***********************************************************************/

static int RunFunction( const char* szFunc )
{
        int iRes = 1;
        int i;
        CmdLineFunc_t* pfFunc = NULL;
        
        for( i = 0; i < ARRAY_SIZE( laxCmdLineFunctions ); i++ ) {
                if( !strcmp( szFunc, laxCmdLineFunctions[ i ].szName ) ) {
                        pfFunc = &laxCmdLineFunctions[ i ];
                        break;
                }
        }

        if( NULL != pfFunc ) {
                /* execute function */

                char cIsHelper = !strncmp( szFunc, "--", 2 );
                if( !cIsHelper )
                        /* options are not tests */
                        printf( "Doing %s\n", szFunc );
                iRes = pfFunc->pfFunc();
                if( !iRes && !cIsHelper )
                        /* options are not tests */
                        ERROR( "Test Failed\n" );
        } else {
                ERROR( "not found: %s\n", szFunc );
                /* not found */
                Usage();
                iRes = 0;
        }

        return iRes;
}

/***********************************************************************
 * !Function: ProcessedOneArg
 * !Descr:    reduces gargc and moves argv[1] to argv[0]
 ***********************************************************************/

static void ProcessedOneArg( void )
{
        if( !largc )
                /* nothing to do */
                return;
        
        largc--;
        memcpy( &largv[ 0 ], &largv[ 1 ], largc * sizeof( largv[ 0 ] ) );
}

/***********************************************************************
 * !Function: Usage
 * !Return:   always 0
 * !Descr:    Prints the usage
 ***********************************************************************/

static int Usage( void )
{
        int i;
        
        printf( "** Usage: test_mem [<test> [<test> ...]]\n" );
        printf( "   Supported tests are:\n" );
        for( i = 0; i < ARRAY_SIZE( laxCmdLineFunctions ); i++ )
                printf( "      %s\n", laxCmdLineFunctions[ i ].szName );

        return 0;
}

static int OptSilent( void )
{
        lcSilent = 1;

        return 1;
}

static int OptEndless( void )
{
        lcEndless = 1;

        return 1;
}

static int OptPatternSize( void )
{
        int iPatternSize = 0;
        
        if( !largc ) {
                ERROR( "Requires <patternsize> argument\n" );
                return 0;
        }

        iPatternSize = simple_strtoul( largv[1], NULL, 10 );

        ProcessedOneArg();

        SetPatternSize( iPatternSize );

        return 1;
}

static int SetPatternSize( int iPatternSize ) 
{
        switch( iPatternSize ) {
        	case 1:
                        PatternFill   = PatternFill1;
                        PatternVerify = PatternVerify1;
                        break;
        	case 2:
                        PatternFill   = PatternFill2;
                        PatternVerify = PatternVerify2;
                        break;
        	case 4:
                        PatternFill   = PatternFill4;
                        PatternVerify = PatternVerify4;
                        break;
	        default:
                        ERROR( "Patternsize not recognized\n" );
                        return 0;
        }

        PRINTF( "Testing Pattern is %i Bytes\n", iPatternSize );
        
        return 1;
}


/***********************************************************************
 * !Function: TestAll
 * !Return:   Runs all tests
 * !Descr:    
 ***********************************************************************/

static int TestAll( void )
{
        int iRes = 1;
        int i;
        
        for( i = 0; i < ARRAY_SIZE( laxCmdLineFunctions ); i++ ) {
                if( laxCmdLineFunctions[ i ].cDoInAll ) {
                        iRes = RunFunction( laxCmdLineFunctions[ i ].szName );
                        if( !iRes )
                                break;
                }
        }

        return iRes;
}

/***********************************************************************
 * !Function: TestBurstSDRAM
 * !Return:   Performs Burst Reads
 * !Descr:    
 ***********************************************************************/

static int TestBurstSDRAM( void )
{
        int    iRes  = 1;
        
        FillTypes_t eFillType = FT_00;

        while( eFillType != FT_NONE ) {
                size_t iSize = 1;

                PRINTF( "  Preparing Source Memory with pattern: %s\n",
                        aszFillTypes[ eFillType ] );
                PatternFill( eFillType, laxMem[ SDRAM_DST ].iSize );
                while( iSize <= 32 ) {
                        PRINTF( "    Using Burst Size %i\n", iSize );
                        
                        CLEAR_SDRAM_DST();
                        
                        CopyBurst( SDRAM_SRC, SDRAM_DST, iSize );
                        
                        PRINTF( "      Verifying\n" );
                        if( !PatternVerify( SDRAM_DST, eFillType ) ) {
                                iRes = 0;
                                break;
                        }
                        
                        iSize *= 2;
                }

                if( !iRes )
                        break;
                
                eFillType++;
        }

        PRINTF( "  Test %s\n", ( iRes ? "successful" : "failed" ) );
        return iRes;
}

/***********************************************************************
 * !Function: TestWriteNOR
 * !Return:   Performs Burst Reads
 * !Descr:    
 ***********************************************************************/

static int TestWriteNOR( void )
{
        int    iRes  = 1;
        
        FillTypes_t eFillType = FT_00;

        while( eFillType != FT_NONE ) {
                PRINTF( "  Preparing Source Memory with pattern: %s\n",
                        aszFillTypes[ eFillType ] );
                PatternFill( eFillType, laxMem[ NOR ].iSize );
                CopyToFlash();
                PRINTF( "   Verifying\n" );
                if( !PatternVerify( NOR, eFillType ) ) {
                        iRes = 0;
                        break;
                }

                eFillType++;
        }

        PRINTF( "  Test %s\n", ( iRes ? "successful" : "failed" ) );
        return iRes;
}

/***********************************************************************
 * !Function: TestBurstCopyNOR
 * !Return:   Performs Burst Reads
 * !Descr:    
 ***********************************************************************/

static int TestBurstCopyNOR( void )
{
        int    iRes = 1;
        size_t iSize = 1;
        
        PRINTF( "  Copying to RAM\n" );

        PRINTF( "  Preparing Test Pattern in SDRAM\n" );
        PatternFill( FT_INC, laxMem[ SDRAM_SRC ].iSize );
        while( iSize <= 32 ) {
                PRINTF( "    Using Burst Size %i\n", iSize );
                
                CopyBurst( NOR, SDRAM_DST, iSize );
                
                PRINTF( "    Verifying SDRAM\n" );
                iRes = PatternVerify( SDRAM_SRC, FT_INC );
                if( !iRes )
                        break;

                iSize *= 2;
        }
        
        return iRes;
}

/***********************************************************************
 * !Function: TestBurstCopyNOR2048
 * !Return:   Performs Burst Reads
 * !Descr:    
 ***********************************************************************/

static int TestBurstCopyNOR2048( void )
{
        int    iRes = 1;
        size_t iBurstSize = 1;
        static const int COPY_SIZE = 2048;
        
        PRINTF( "  Copying to RAM in 2kB Blocks\n" );

        PRINTF( "  Preparing Test Pattern in SDRAM\n" );
        PatternFill( FT_INC, laxMem[ SDRAM_SRC ].iSize );

        while( iBurstSize <= 32 ) {
                int iSizeToCopy = laxMem[ NOR ].iSize;
                uchar* pucNOR = laxMem[ NOR ].pucMem;
                uchar* pucUpper = laxMem[ SDRAM_DST ].pucMem;

                if( iSizeToCopy % COPY_SIZE ) {
                        ERROR( "Invalid size %i, not a multiple of %i\n",
                               iSizeToCopy, COPY_SIZE );
                        iRes = 0;
                        break;
                }
                
                PRINTF( "    Using Burst Size %i\n", iBurstSize );

                while( iSizeToCopy ) {
                        CopyBurstBlock( pucNOR, pucUpper, iBurstSize, COPY_SIZE );
                        iSizeToCopy -= COPY_SIZE;
                        if( !iRes )
                                break;
                }
                
                iRes = PatternVerify( SDRAM_SRC, FT_INC );
                if( !iRes )
                        break;
                
                iBurstSize *= 2;
        }
        
        return iRes;
}

/***********************************************************************
 * !Function: TestBurstNOR
 * !Return:   Performs Burst Reads
 * !Descr:    
 ***********************************************************************/

static int TestBurstNOR( void )
{
        int    iRes  = 1;
        
        FillTypes_t eFillType = FT_00;

        while( eFillType != FT_NONE ) {
                size_t iSize = 1;

                PRINTF( "  Preparing Source Memory with pattern: %s\n",
                        aszFillTypes[ eFillType ] );
                PatternFill( eFillType, laxMem[ NOR ].iSize );
                iRes = CopyToFlash();
                if( !iRes )
                        break;

                PRINTF( "  Copying to RAM\n" );
                while( iSize <= 32 ) {
                        PRINTF( "    Using Burst Size %i\n", iSize );

                        CopyBurst( NOR, SDRAM_DST, iSize );
                        PRINTF( "      Verifying\n" );
                        iRes = PatternVerify( SDRAM_DST, eFillType );
                        if( !iRes )
                                break;
                        
                        iSize *= 2;
                }

                if( !iRes )
                        break;
                
                eFillType++;
        }

        PRINTF( "  Test %s\n", ( iRes ? "successful" : "failed" ) );
        return iRes;
}

static void CopyBurst( MemInfoType_t eSrc, MemInfoType_t eDst,
                       size_t iBurstSize )
{
        uchar* pucSrc = laxMem[ eSrc ].pucMem;
        uchar* pucDst = laxMem[ eDst ].pucMem;
        size_t iMin = ( laxMem[ eSrc ].iSize > laxMem[ eDst ].iSize ) ?
                laxMem[ eDst ].iSize :
                laxMem[ eSrc ].iSize;

        PRINTF( "      Copying %i KiB\n", iMin / 1024 );

        CopyBurstBlock( pucSrc, pucDst, iBurstSize, iMin );
}

static void CopyBurstBlock( uchar* pucSrc, uchar* pucDst,
                            size_t iBurstSize, size_t iCopySize )
{
        CopyBurstFunc_t pfCopy = NULL;

        switch( iBurstSize ) {
        	case 1:  pfCopy = MemCpyBurst1;  break;
        	case 2:  pfCopy = MemCpyBurst2;  break;
        	case 4:  pfCopy = MemCpyBurst4;  break;
        	case 8:  pfCopy = MemCpyBurst8;  break;
        	case 16: pfCopy = MemCpyBurst16; break;
        	case 32: pfCopy = MemCpyBurst32; break;
                default: ERROR( "Invalid size %i\n", iBurstSize ); return;
        }

        if( iCopySize % iBurstSize )
                ERROR( "Invalid size %i, not a multiple of %i\n",
                       iCopySize, iBurstSize );
        
        while( iCopySize ) {
                pfCopy( pucSrc, pucDst );
                
                pucSrc    += iBurstSize;
                pucDst    += iBurstSize;
                iCopySize -= iBurstSize;
        }
}

static int CopyToFlash( void )
{
        char acCmd[ 128 ];

        PRINTF( "      Erasing flash\n" );
        if( laxMem[ SDRAM_SRC ].iSize < laxMem[ NOR ].iSize ) {
                ERROR( "SDRAM_SRC is less than NOR\n" );
                return 0;
        }

        sprintf( acCmd, "erase %x +%x",
                 laxMem[ NOR ].pucMem, laxMem[ NOR ].iSize );
        if( run_command( acCmd, 0 ) != 1 ) {
                ERROR( "cmd %s failed\n", acCmd );
                return 0;
        }
        
        PRINTF( "      Programming flash\n" );
        sprintf( acCmd, "cp.b %x %x %x",
                 laxMem[ SDRAM_SRC ].pucMem, laxMem[ NOR ].pucMem, laxMem[ NOR ].iSize );
        if( run_command( acCmd, 0 ) != 1 ) {
                ERROR( "cmd %s failed\n", acCmd );
                return 0;
        }

        return 1;
}

static void PatternFill1( FillTypes_t eFillType, size_t iSize )
{
        uchar   ucVal  = 0;
        uchar*  pucMem = laxMem[ SDRAM_SRC ].pucMem;
        int     i;
        
        for( i = 0; i < iSize; i++, pucMem++ ) {
                UpdateVal1( eFillType, &ucVal );
                *pucMem = ucVal;
        }
}

static int PatternVerify1( MemInfoType_t eMemType, FillTypes_t eFillType )
{
        int   iRes  = 1;
        uchar ucExp = 0;
        const uchar* pucMem = laxMem[ eMemType ].pucMem;
        size_t iSize        = laxMem[ eMemType ].iSize;
        int i;
        
        for( i = 0; i < iSize; i++, pucMem++ ) {
                uchar ucVal;
                
                UpdateVal1( eFillType, &ucExp );

                ucVal = *pucMem;
                if( ucExp != ucVal ) {
                        ERROR( "Memory mismatch @ 0x%08x, expected 0x%02x, have 0x%02x\n",
                               pucMem, ucExp, ucVal );
                        iRes = 0;
                        break;
                }
        }

        return iRes;
}

static void UpdateVal1( FillTypes_t eFillType, /*@inout@*/ unsigned char* pucVal )
{
        switch( eFillType ) {
        	case FT_00:   *pucVal = 0x00; break;
        	case FT_FF:   *pucVal = 0xff; break;
                case FT_INC:  *pucVal = (*pucVal)++; break;
                case FT_NONE: ERROR( "FT_NONE not supported\n" ); break;
        }
}


static void PatternFill4( FillTypes_t eFillType, size_t iSize )
{
        iSize /= 4;
        unsigned int   uiVal  = 0;
        unsigned int*  puiMem = (unsigned int*) laxMem[ SDRAM_SRC ].pucMem;
        int     i;
        
        for( i = 0; i < iSize; i++, puiMem++ ) {
                UpdateVal4( eFillType, &uiVal );
                *puiMem = uiVal;
        }
}

static int PatternVerify4( MemInfoType_t eMemType, FillTypes_t eFillType )
{
        int   iRes  = 1;
        unsigned int uiExp = 0;
        const unsigned int* puiMem = (const unsigned int*) laxMem[ eMemType ].pucMem;
        size_t iSize        = laxMem[ eMemType ].iSize / 4;
        int i;
        
        for( i = 0; i < iSize; i++, puiMem++ ) {
                unsigned int uiVal;
                
                UpdateVal4( eFillType, &uiExp );

                uiVal = *puiMem;
                if( uiExp != uiVal ) {
                        ERROR( "Memory mismatch @ 0x%08x, expected 0x%08x, have 0x%08x\n",
                               puiMem, uiExp, uiVal );
                        iRes = 0;
                        break;
                }
        }

        return iRes;
}

static void UpdateVal4( FillTypes_t eFillType, /*@inout@*/ unsigned int* puiVal )
{
        switch( eFillType ) {
        	case FT_00:   *puiVal = 0x00; break;
        	case FT_FF:   *puiVal = 0xffffffff; break;
                case FT_INC:  *puiVal = (*puiVal)++; break;
                case FT_NONE: ERROR( "FT_NONE not supported\n" ); break;
        }
}


static void PatternFill2( FillTypes_t eFillType, size_t iSize )
{
        unsigned short   uiVal  = 0;
        unsigned short*  puiMem = (unsigned short*) laxMem[ SDRAM_SRC ].pucMem;
        int     i;
        iSize /= 2;
        
        for( i = 0; i < iSize; i++, puiMem++ ) {
                UpdateVal2( eFillType, &uiVal );
                *puiMem = uiVal;
        }
}

static int PatternVerify2( MemInfoType_t eMemType, FillTypes_t eFillType )
{
        int   iRes  = 1;
        unsigned short  uiExp = 0;
        const unsigned short* puiMem = (const unsigned short*) laxMem[ eMemType ].pucMem;
        size_t iSize        = laxMem[ eMemType ].iSize / 2;
        int i;
        
        for( i = 0; i < iSize; i++, puiMem++ ) {
                unsigned short uiVal;
                
                UpdateVal2( eFillType, &uiExp );

                uiVal = *puiMem;
                if( uiExp != uiVal ) {
                        ERROR( "Memory mismatch @ 0x%08x, expected 0x%04x, have 0x%04x\n",
                               puiMem, uiExp, uiVal );
                        iRes = 0;
                        break;
                }
        }

        return iRes;
}

static void UpdateVal2( FillTypes_t eFillType, /*@inout@*/ unsigned short* puiVal )
{
        switch( eFillType ) {
        	case FT_00:   *puiVal = 0x0000; break;
        	case FT_FF:   *puiVal = 0xffff; break;
                case FT_INC:  *puiVal = (*puiVal)++; break;
                case FT_NONE: ERROR( "FT_NONE not supported\n" ); break;
        }
}

