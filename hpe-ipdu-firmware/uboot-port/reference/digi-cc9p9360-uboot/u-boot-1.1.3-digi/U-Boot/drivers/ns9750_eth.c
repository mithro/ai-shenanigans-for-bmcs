/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: ns9750_eth.c,v 1.3 2005/01/12 13:04:28 jjaeger Exp $
 * @Author: Markus Pietrek
 * @Descr: Ethernet driver for the NS9750. Uses DMA Engine with polling
 *         interrupt status. But interrupts are not enabled.
 *         Only one tx buffer descriptor and the RXA buffer descriptor are used
 *         Currently no transmit lockup handling is included. eth_send has a 5s
 *         timeout for sending frames. No retransmits are performed when an
 *         error occurs.
 * @References: [1] NS9750 Hardware Reference, December 2003
 *              [2] Intel LXT971 Datasheet #249414 Rev. 02
 *              [3] NS7520 Linux Ethernet Driver
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 *
 ***********************************************************************/
/***********************************************************************
 *  @History:
 *     2004/08/30 : forcing 100Mbps/half if auto-negotiation fails
 ***********************************************************************/

#include <common.h>
#include <net.h>		/* NetSendPacket */

#include "ns9750_eth.h"		/* for Ethernet and PHY */
#ifdef CONFIG_NS9360
#include "ns9750_bbus.h"
#endif

#ifdef CONFIG_DRIVER_NS9750_ETHERNET

/* some definition to make transistion to linux easier */

#define NS9750_DRIVER_NAME	"eth"
#define KERN_WARNING 		"Warning:"
#define KERN_ERR 		"Error:"
#define KERN_INFO 		"Info:"

#if 0
# define DEBUG
#endif

#ifdef	DEBUG
# define printk			printf

# define DEBUG_INIT		0x0001
# define DEBUG_MINOR		0x0002
# define DEBUG_RX		0x0004
# define DEBUG_TX		0x0008
# define DEBUG_INT		0x0010
# define DEBUG_POLL		0x0020
# define DEBUG_LINK		0x0040
# define DEBUG_MII		0x0100
# define DEBUG_MII_LOW		0x0200
# define DEBUG_MEM		0x0400
# define DEBUG_ERROR		0x4000
# define DEBUG_ERROR_CRIT	0x8000

static int nDebugLvl = DEBUG_ERROR_CRIT;

# define DEBUG_ARGS0( FLG, a0 ) if( ( nDebugLvl & (FLG) ) == (FLG) ) \
		printf("%s: " a0, __FUNCTION__, 0, 0, 0, 0, 0, 0 )
# define DEBUG_ARGS1( FLG, a0, a1 ) if( ( nDebugLvl & (FLG) ) == (FLG)) \
		printf("%s: " a0, __FUNCTION__, (int)(a1), 0, 0, 0, 0, 0 )
# define DEBUG_ARGS2( FLG, a0, a1, a2 ) if( (nDebugLvl & (FLG)) ==(FLG))\
		printf("%s: " a0, __FUNCTION__, (int)(a1), (int)(a2), 0, 0,0,0 )
# define DEBUG_ARGS3( FLG, a0, a1, a2, a3 ) if((nDebugLvl &(FLG))==(FLG))\
		printf("%s: "a0,__FUNCTION__,(int)(a1),(int)(a2),(int)(a3),0,0,0)
# define DEBUG_FN( FLG ) if( (nDebugLvl & (FLG)) == (FLG) ) \
		printf("\r%s:line %d\n", (int)__FUNCTION__, __LINE__, 0,0,0,0);
# define ASSERT( expr, func ) if( !( expr ) ) { \
        	printf( "Assertion failed! %s:line %d %s\n", \
        	(int)__FUNCTION__,__LINE__,(int)(#expr),0,0,0); \
        	func }
#else /* DEBUG */
# define printk(...)
# define DEBUG_ARGS0( FLG, a0 )
# define DEBUG_ARGS1( FLG, a0, a1 )
# define DEBUG_ARGS2( FLG, a0, a1, a2 )
# define DEBUG_ARGS3( FLG, a0, a1, a2, a3 )
# define DEBUG_FN( n )
# define ASSERT(expr, func)
#endif /* DEBUG */

#define NS9750_MII_NEG_DELAY      	(5*CFG_HZ) /* in s */
#define TX_TIMEOUT			(5*CFG_HZ) /* in s */
#define SPREAD_SPECTRUM_PERCENTAGE	(4)	   /* 4% */

/* @TODO move it to eeprom.h */
#define FS_EEPROM_AUTONEG_MASK		0x7
#define FS_EEPROM_AUTONEG_SPEED_MASK	0x1
#define FS_EEPROM_AUTONEG_SPEED_10	0x0
#define FS_EEPROM_AUTONEG_SPEED_100	0x1
#define FS_EEPROM_AUTONEG_DUPLEX_MASK	0x2
#define FS_EEPROM_AUTONEG_DUPLEX_HALF	0x0
#define FS_EEPROM_AUTONEG_DUPLEX_FULL	0x2
#define FS_EEPROM_AUTONEG_ENABLE_MASK	0x4
#define FS_EEPROM_AUTONEG_DISABLE	0x0
#define FS_EEPROM_AUTONEG_ENABLE	0x4

/* buffer descriptors taken from [1] p.306 */
typedef struct
{
	unsigned int* punSrc;
	unsigned int unLen;	/* 11 bits */
	unsigned int* punDest;	/* unused */
	union {
		unsigned int unReg;
		struct {
			unsigned uStatus : 16;
			unsigned uRes : 12;
			unsigned uFull : 1;
			unsigned uEnable : 1;
			unsigned uInt : 1;
			unsigned uWrap : 1;
		} bits;
	} s;
} rx_buffer_desc_t;

typedef struct
{
	unsigned int* punSrc;
	unsigned int unLen;	/* 10 bits */
	unsigned int* punDest;	/* unused */
	union {
		unsigned int unReg; /* only 32bit accesses may done to NS9750
				     * eth engine */
		struct {
			unsigned uStatus : 16;
			unsigned uRes : 12;
			unsigned uFull : 1;
			unsigned uLast : 1;
			unsigned uInt : 1;
			unsigned uWrap : 1;
		} bits;
	} s;
} tx_buffer_desc_t;

static int ns9750_eth_reset( void );
static void ns9750_eth_reset_mac( void );

static void ns9750_link_force( void );
static void ns9750_link_auto_negotiate( void );
static void ns9750_link_update_egcr( void );
static void ns9750_link_print_changed( void );

/* the PHY stuff */

static char ns9750_mii_identify_phy( void );
static unsigned short ns9750_mii_read( unsigned short uiRegister );
static void ns9750_mii_write( unsigned short uiRegister, unsigned short uiData );
static unsigned int ns9750_mii_get_clock_divisor( unsigned int unMaxMDIOClk );
static unsigned int ns9750_mii_poll_busy( void );

static unsigned int nPhyMaxMdioClock = PHY_MDIO_MAX_CLK;
static unsigned char ucLinkMode =      FS_EEPROM_AUTONEG_ENABLE;
static unsigned int uiLastLinkStatus;
static PhyType phyDetected = PHY_NONE;
/* time network stack should be delayed after auto-negotiation to give switch
 * more time. */
static unsigned int uiPostAutoNegDelay = 0;

/* we use only one tx buffer descriptor */
static tx_buffer_desc_t* pTxBufferDesc =
	(tx_buffer_desc_t*) get_eth_reg_addr( NS9750_ETH_TXBD );

/* we use only one rx buffer descriptor of the 4 */
static rx_buffer_desc_t rxBufferDesc[PKTBUFSRX];
static uchar rxBuffer[PKTBUFSRX][(1522 + (0x1f)) & ~0x1f];

/***********************************************************************
 * @Function: eth_init
 * @Return: -1 on failure otherwise 0
 * @Descr: Initializes the ethernet engine and uses either FS Forth's default
 *         MAC addr or the one in environment
 ***********************************************************************/

int eth_init( bd_t* pbis )
{
	/* This default MAC Addr is reserved by FS Forth-Systeme for the case of
	   EEPROM failures */
	int i;

	DEBUG_FN( DEBUG_INIT );

#ifdef CONFIG_NS9360
	for( i=50; i<=64; i++)
		set_gpio_cfg_reg_val( i, NS9750_GPIO_CFG_FUNC_0 );
#endif /*CONFIG_NS9360 */

	/* no need to check for hardware */

	if( !ns9750_eth_reset() )
		return -1;

        /* configure ethernet address */
        eth_use_mac_from_env( pbis );

	*get_eth_reg_addr( NS9750_ETH_MAC2 ) = NS9750_ETH_MAC2_CRCEN |
		NS9750_ETH_MAC2_PADEN |
		NS9750_ETH_MAC2_FULLD;

	/* enable hardware */
	/* prepare DMA descriptors */
	/* NetRxPackets[ 0 ] is initialized before eth_init is called and never
	   changes. NetRxPackets is 32bit aligned */

	for (i = 0; i < PKTBUFSRX; ++i) {
		rxBufferDesc[i].punSrc = (unsigned int*) (rxBuffer[i]);
		rxBufferDesc[i].unLen = 1522;
		rxBufferDesc[i].s.bits.uWrap = !(i < PKTBUFSRX - 1);
		rxBufferDesc[i].s.bits.uInt = 1;
		rxBufferDesc[i].s.bits.uEnable = 1;
		rxBufferDesc[i].s.bits.uFull = 0;
	}

	*get_eth_reg_addr( NS9750_ETH_RXAPTR ) = (unsigned int)rxBufferDesc;
	*get_eth_reg_addr( NS9750_ETH_RXBPTR ) = 0;
	*get_eth_reg_addr( NS9750_ETH_RXCPTR ) = 0;
	*get_eth_reg_addr( NS9750_ETH_RXDPTR ) = 0;

	udelay(1); /* This seems to be only needed when compiled under cygwin?? */

	/* pTxBufferDesc is the first possible buffer descriptor */
	*get_eth_reg_addr( NS9750_ETH_TXPTR ) = 0x0;

	*get_eth_reg_addr( NS9750_ETH_TXBD ) = 0x00212000;
	*get_eth_reg_addr( NS9750_ETH_TXBD1 ) = 0x00000400;
	*get_eth_reg_addr( NS9750_ETH_TXBD2 ) = 0x00000000;
	*get_eth_reg_addr( NS9750_ETH_TXBD3 ) = 0x10000000;
	*get_eth_reg_addr( NS9750_ETH_TXBD4 ) = 0x00212400;
	*get_eth_reg_addr( NS9750_ETH_TXBD5 ) = 0x00000200;
	*get_eth_reg_addr( NS9750_ETH_TXBD6 ) = 0x00000000;
	*get_eth_reg_addr( NS9750_ETH_TXBD7 ) = 0xB0000000;

	/* enable receive and transmit FIFO, use 10/100 Mbps MII */
	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) =
		NS9750_ETH_EGCR1_ERX |
		NS9750_ETH_EGCR1_ETX |
		NS9750_ETH_EGCR1_ERXINIT;

	/* [1] Tab. 221 states less than 5us */
	udelay( 5 );
	while( !(*get_eth_reg_addr(NS9750_ETH_EGSR) & NS9750_ETH_EGSR_RXINIT))
		/* wait for finish */
		udelay( 1 );

        *get_eth_reg_addr(NS9750_ETH_EGSR) = NS9750_ETH_EGSR_RXINIT;

	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) &= ~NS9750_ETH_EGCR1_ERXINIT;
	*get_eth_reg_addr( NS9750_ETH_EGCR2 ) = NS9750_ETH_EGCR2_STEN;


	*get_eth_reg_addr( NS9750_ETH_MAC1 ) = NS9750_ETH_MAC1_RXEN;
	*get_eth_reg_addr( NS9750_ETH_SUPP ) &= ~NS9750_ETH_SUPP_RPERMII;

	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) =
		NS9750_ETH_EGCR1_ERX |
		NS9750_ETH_EGCR1_ETX |
		NS9750_ETH_EGCR1_ERXDMA |
		NS9750_ETH_EGCR1_ETXDMA |
		NS9750_ETH_EGCR1_ERXSHT;

	/* acknowledge status register */
	udelay( 1000 );
	*get_eth_reg_addr(NS9750_ETH_EINTR) |= *get_eth_reg_addr(NS9750_ETH_EINTR);

	return 0;
}

/***********************************************************************
 * @Function: eth_send
 * @Return: -1 on timeout otherwise 1
 * @Descr: sends one frame by DMA
 ***********************************************************************/

int eth_send( volatile void* pPacket, int nLen )
{
	ulong ulTimeout;
	ulong ulCheck;

	DEBUG_FN( DEBUG_TX );

	/* clear old status values */
	*get_eth_reg_addr(NS9750_ETH_EINTR)&=*get_eth_reg_addr(NS9750_ETH_EINTR)&
		NS9750_ETH_EINTR_TX_MA;

	/* prepare Tx Descriptors */

	pTxBufferDesc->punSrc = (unsigned int*) pPacket; /* pPacket is 32bit
							  * aligned */
	pTxBufferDesc->unLen = nLen;
	/* only 32bit accesses allowed. wrap, full, interrupt and enabled to 1 */
	pTxBufferDesc->s.unReg = 0xf0000000;
	/* pTxBufferDesc is the first possible buffer descriptor */
	*get_eth_reg_addr( NS9750_ETH_TXPTR ) = 0x0;

	/* enable processor for next frame */

	*get_eth_reg_addr( NS9750_ETH_EGCR2 ) &= ~NS9750_ETH_EGCR2_TCLER;
	*get_eth_reg_addr( NS9750_ETH_EGCR2 ) |= NS9750_ETH_EGCR2_TCLER;

	ulTimeout = get_timer( 0 );

	DEBUG_ARGS0(DEBUG_TX|DEBUG_MINOR,"Waiting for transmission to finish\n");
	
	ulCheck = *get_eth_reg_addr( NS9750_ETH_EINTR );
	while( !(ulCheck & (NS9750_ETH_EINTR_TXDONE | NS9750_ETH_EINTR_TXERR) ) ) {
		/* do nothing, wait for completion */
		if( get_timer( 0 ) - ulTimeout > TX_TIMEOUT ) {
			DEBUG_ARGS0( DEBUG_TX, "Transmit Timed out\n" );
			return -1;
		}
		ulCheck = *get_eth_reg_addr( NS9750_ETH_EINTR );
	}
	DEBUG_ARGS0( DEBUG_TX|DEBUG_MINOR, "transmitted...\n");

        return 0;
}

/***********************************************************************
 * @Function: eth_rx
 * @Return: size of last frame in bytes or 0 if no frame available
 * @Descr: gives one frame to U-Boot which has been copied by DMA engine already
 *         to NetRxPackets[ 0 ].
 ***********************************************************************/

int eth_rx( void )
{
	unsigned int unStatus;
	int i;

	unStatus = *get_eth_reg_addr(NS9750_ETH_EINTR) & NS9750_ETH_EINTR_RX_MA;

	if( !unStatus )
		/* no packet available, return immediately */
		return 0;

	DEBUG_FN( DEBUG_RX );

	/* acknowledge status register */
	*get_eth_reg_addr(NS9750_ETH_EINTR) = unStatus;

	if (unStatus & NS9750_ETH_EINTR_RXDONEA)  {
		for (i = 0; i < PKTBUFSRX; ++i) {
			if (rxBufferDesc[i].s.bits.uFull) {
				int len = rxBufferDesc[i].unLen - 4;
				NetReceive(rxBuffer[i], len);

				rxBufferDesc[i].unLen = 1522;
				rxBufferDesc[i].s.bits.uFull = 0;
				*get_eth_reg_addr(NS9750_ETH_RXFREE) |= 0x1;
			}
		}
	}

	return 0;
}

/***********************************************************************
 * @Function: eth_halt
 * @Return: n/a
 * @Descr: stops the ethernet engine
 ***********************************************************************/

void eth_halt( void )
{
	DEBUG_FN( DEBUG_INIT );

	*get_eth_reg_addr( NS9750_ETH_MAC1 ) &= ~NS9750_ETH_MAC1_RXEN;
	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) &= ~(NS9750_ETH_EGCR1_ERX |
						   NS9750_ETH_EGCR1_ERXDMA |
						   NS9750_ETH_EGCR1_ETX |
						   NS9750_ETH_EGCR1_ETXDMA );
}

/***********************************************************************
 * @Function: ns9750_eth_reset
 * @Return: 0 on failure otherwise 1
 * @Descr: resets the ethernet interface and the PHY,
 *         performs auto negotiation or fixed modes
 ***********************************************************************/

static int ns9750_eth_reset( void )
{
	DEBUG_FN( DEBUG_MINOR );

        ns9750_eth_reset_mac();

	/* reset and initialize PHY */
	*get_eth_reg_addr( NS9750_ETH_SUPP ) = NS9750_ETH_SUPP_RPERMII;

	*get_eth_reg_addr( NS9750_ETH_MAC1 ) = NS9750_ETH_MAC1_RPEMCSR |
						NS9750_ETH_MAC1_RPERFUN |
						NS9750_ETH_MAC1_RPEMCST |
						NS9750_ETH_MAC1_RPETFUN;

	/* we don't support hot plugging of PHY, therefore we don't reset
	   phyDetected and nPhyMaxMdioClock here. The risk is if the setting is
	   incorrect the first open
	   may detect the PHY correctly but succeding will fail
	   For reseting the PHY and identifying we have to use the standard
	   MDIO CLOCK value 2.5 MHz only after hardware reset
	   After having identified the PHY we will do faster */

	*get_eth_reg_addr( NS9750_ETH_MCFG ) =
	    ns9750_mii_get_clock_divisor( nPhyMaxMdioClock );

#ifdef PHY_RESET
	/* reset PHY */
	ns9750_mii_write( PHY_COMMON_CTRL, PHY_COMMON_CTRL_RESET );
	ns9750_mii_write( PHY_COMMON_CTRL, 0 );

	/* @TODO check time */
	udelay( 3000 ); /* [2] p.70 says at least 300us reset recovery time. But
			   go sure, it didn't worked stable at higher timer
			   frequencies under LxNETES-2.x */
#endif /* PHY_RESET */

	/* MII clock has been setup to default, ns9750_mii_identify_phy should
	   work for all */

	if( !ns9750_mii_identify_phy() ) {
	    printf( "Unsupported PHY, aborting\n");
	    return 0;
	}

	/* now take the highest MDIO clock possible after detection */
	*get_eth_reg_addr( NS9750_ETH_MCFG ) =
	    ns9750_mii_get_clock_divisor( nPhyMaxMdioClock );


	/* PHY has been detected, so there can be no abort reason and we can
	   finish initializing ethernet */

	uiLastLinkStatus = 0xff; /* undefined */

	if((ucLinkMode&FS_EEPROM_AUTONEG_ENABLE_MASK)==FS_EEPROM_AUTONEG_DISABLE)
		/* use parameters defined */
		ns9750_link_force();
	else
		ns9750_link_auto_negotiate();

#if !defined(CONFIG_NS9750ACCORD) && !defined (CONFIG_CC9C) && !defined (CONFIG_CCW9C)
	if( phyDetected == PHY_LXT971A )
		/* set LED2 to link mode */
		ns9750_mii_write( PHY_LXT971_LED_CFG,
				  PHY_LXT971_LED_CFG_LINK_ACT <<
				  PHY_LXT971_LED_CFG_SHIFT_LED2);
#endif

	return 1;
}

/***********************************************************************
 * @Function: ns9750_eth_reset_mac
 * @Return: 0 on failure otherwise 1
 * @Descr: resets the MAC 
 ***********************************************************************/

static void ns9750_eth_reset_mac( void )
{
	DEBUG_FN( DEBUG_MINOR );

	/* Reset MAC */
	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) |= (NS9750_ETH_EGCR1_MAC_HRST |
							NS9750_ETH_EGCR1_ERX |
							NS9750_ETH_EGCR1_ETX);
	udelay( 5 ); 		/* according to [1], p.322 */
	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) &= ~NS9750_ETH_EGCR1_MAC_HRST;
}

/***********************************************************************
 * @Function: ns9750_link_force
 * @Return: void
 * @Descr: configures eth and MII to use the link mode defined in
 *         ucLinkMode
 ***********************************************************************/

static void ns9750_link_force( void )
{
	unsigned short uiControl;

	DEBUG_FN( DEBUG_LINK );

	uiControl = ns9750_mii_read( PHY_COMMON_CTRL );
	uiControl &= ~( PHY_COMMON_CTRL_SPD_MA |
			PHY_COMMON_CTRL_AUTO_NEG |
			PHY_COMMON_CTRL_DUPLEX );

	uiLastLinkStatus = 0;

	if( ( ucLinkMode & FS_EEPROM_AUTONEG_SPEED_MASK ) ==
	    FS_EEPROM_AUTONEG_SPEED_100 ) {
	    uiControl |= PHY_COMMON_CTRL_SPD_100;
#ifdef CONFIG_NS9750ACCORD
	    uiLastLinkStatus |= PHY_RTL8201_STAT2_100BTX;
#elif defined (CONFIG_CC9C) || (CONFIG_CCW9C)
	    uiLastLinkStatus |= PHY_ICS1893_QPSTAT_100BTX;
#else
	    uiLastLinkStatus |= PHY_LXT971_STAT2_100BTX;
#endif
	} else
	    uiControl |= PHY_COMMON_CTRL_SPD_10;

	if( ( ucLinkMode & FS_EEPROM_AUTONEG_DUPLEX_MASK ) ==
	    FS_EEPROM_AUTONEG_DUPLEX_FULL ) {
	    uiControl |= PHY_COMMON_CTRL_DUPLEX;
#ifdef CONFIG_NS9750ACCORD
	    uiLastLinkStatus |= PHY_RTL8201_STAT2_DUPLEX_MODE;
#elif defined (CONFIG_CC9C) || (CONFIG_CCW9C)
	    uiLastLinkStatus |= PHY_ICS1893_QPSTAT_DUPLEX;
#else
	    uiLastLinkStatus |= PHY_LXT971_STAT2_DUPLEX_MODE;
#endif
	}

	ns9750_mii_write( PHY_COMMON_CTRL, uiControl );

	ns9750_link_print_changed();
	ns9750_link_update_egcr();
}

/***********************************************************************
 * @Function: ns9750_link_auto_negotiate
 * @Return: void
 * @Descr: performs auto-negotation of link.
 ***********************************************************************/

static void ns9750_link_auto_negotiate( void )
{
	unsigned long ulStartJiffies;
	unsigned short uiStatus;

	DEBUG_FN( DEBUG_LINK );

	uiStatus = ns9750_mii_read( PHY_COMMON_STAT );
	if( ( uiStatus &
	      (PHY_COMMON_STAT_AN_COMP | PHY_COMMON_STAT_LNK_STAT)) ==
	    (PHY_COMMON_STAT_AN_COMP | PHY_COMMON_STAT_LNK_STAT) ) {
		ns9750_link_print_changed();
		ns9750_link_update_egcr();
		return;
	}

	/* run auto-negotation */
	/* define what we are capable of */
	ns9750_mii_write( PHY_COMMON_AUTO_ADV,
			  PHY_COMMON_AUTO_ADV_100BTXFD |
			  PHY_COMMON_AUTO_ADV_100BTX |
			  PHY_COMMON_AUTO_ADV_10BTFD |
			  PHY_COMMON_AUTO_ADV_10BT |
			  PHY_COMMON_AUTO_ADV_802_3 );
	/* start auto-negotiation */
	ns9750_mii_write( PHY_COMMON_CTRL,
			  PHY_COMMON_CTRL_AUTO_NEG |
			  PHY_COMMON_CTRL_RES_AUTO );

	/* wait for completion */

	ulStartJiffies = get_ticks();
	while( get_ticks() < ulStartJiffies + NS9750_MII_NEG_DELAY ) {
		uiStatus = ns9750_mii_read( PHY_COMMON_STAT );
		if( ( uiStatus &
		      (PHY_COMMON_STAT_AN_COMP | PHY_COMMON_STAT_LNK_STAT)) ==
		    (PHY_COMMON_STAT_AN_COMP | PHY_COMMON_STAT_LNK_STAT) ) {
			/* lucky we are, auto-negotiation succeeded */
			ns9750_link_print_changed();
			ns9750_link_update_egcr();

                        /* It has been observed that the
                         * D-Link Gigabit Switch in combination with an LXT971
                         * (CC9P9360/CC9U) isn't ready after
                         * auto-negotiation complete (this is done only on
                         * hard-reset).
                         * Probably, the switch
                         * internally still needs to update some stuff as well
                         * before being able to receive/transmit.
                         * So, we have a TFTP timeout on first access, lasting
                         * about 4s. Adding a short delay helps here, but
                         * isn't noticed normally.
                         * This has not been noted on a CCW9C using a different
                         * PHY */
                        udelay( uiPostAutoNegDelay );

			return;
		}
	}

	printf( KERN_WARNING NS9750_DRIVER_NAME
		":auto-negotiation timed out, forcing 10Mbps/Half\n" );

	/* force mode */
	ucLinkMode = FS_EEPROM_AUTONEG_SPEED_10 | FS_EEPROM_AUTONEG_DUPLEX_HALF;
	ns9750_link_force();
}

/***********************************************************************
 * @Function: ns9750_link_update_egcr
 * @Return: void
 * @Descr: updates the EGCR and MAC2 link status after mode change or
 *         auto-negotation
 ***********************************************************************/

static void ns9750_link_update_egcr( void )
{
	unsigned int unEGCR;
	unsigned int unMAC2;
	unsigned int unIPGT;

	DEBUG_FN( DEBUG_LINK );

	unEGCR = *get_eth_reg_addr( NS9750_ETH_EGCR1 );
	unMAC2 = *get_eth_reg_addr( NS9750_ETH_MAC2 );
	unIPGT = *get_eth_reg_addr( NS9750_ETH_IPGT ) & ~NS9750_ETH_IPGT_MA;

	unMAC2 &= ~NS9750_ETH_MAC2_FULLD;
#ifdef CONFIG_NS9750ACCORD
	if( (uiLastLinkStatus & PHY_RTL8201_STAT2_DUPLEX_MODE)
	    == PHY_RTL8201_STAT2_DUPLEX_MODE ) {
		unMAC2 |= NS9750_ETH_MAC2_FULLD;
		unIPGT |= 0x15;	/* see [1] p. 339 */
	}
#elif defined (CONFIG_CC9C) || (CONFIG_CCW9C)
	if( (uiLastLinkStatus & PHY_ICS1893_QPSTAT_DUPLEX)
	    == PHY_ICS1893_QPSTAT_DUPLEX ) {
		unMAC2 |= NS9750_ETH_MAC2_FULLD;
		unIPGT |= 0x15;	/* see [1] p. 339 */
	}
#else
	if( (uiLastLinkStatus & PHY_LXT971_STAT2_DUPLEX_MODE)
	    == PHY_LXT971_STAT2_DUPLEX_MODE ) {
		unMAC2 |= NS9750_ETH_MAC2_FULLD;
		unIPGT |= 0x15;	/* see [1] p. 339 */
	}
#endif
	else
		unIPGT |= 0x12;	/* see [1] p. 339 */

	*get_eth_reg_addr( NS9750_ETH_MAC2 ) = unMAC2;
	*get_eth_reg_addr( NS9750_ETH_EGCR1 ) = unEGCR;
	*get_eth_reg_addr( NS9750_ETH_IPGT ) = unIPGT;
}

/***********************************************************************
 * @Function: ns9750_link_print_changed
 * @Return: void
 * @Descr: checks whether the link status has changed and if so prints
 *         the new mode
 ***********************************************************************/

static void ns9750_link_print_changed( void )
{
	unsigned short uiStatus;
	unsigned short uiControl;

	DEBUG_FN( DEBUG_LINK );

	uiControl = ns9750_mii_read( PHY_COMMON_CTRL );

	if( (uiControl & PHY_COMMON_CTRL_AUTO_NEG) == PHY_COMMON_CTRL_AUTO_NEG) {
		/* PHY_COMMON_STAT_LNK_STAT is only set on autonegotiation */
		uiStatus = ns9750_mii_read( PHY_COMMON_STAT );

		if( !( uiStatus & PHY_COMMON_STAT_LNK_STAT) ) {
			printk( KERN_WARNING NS9750_DRIVER_NAME ": link down\n");
			/* @TODO Linux: carrier_off */
		} else {
			/* @TODO Linux: carrier_on */
#ifdef CONFIG_NS9750ACCORD
	unsigned short uiStatus_bak;
			if( phyDetected == PHY_RTL8201 ) {
				uiStatus = ns9750_mii_read( PHY_COMMON_AUTO_ADV );
				uiStatus &= (PHY_RTL8201_STAT2_100BTX);
				uiStatus_bak = uiStatus;
				uiStatus = ns9750_mii_read( PHY_COMMON_CTRL );
				uiStatus &= (PHY_RTL8201_STAT2_DUPLEX_MODE |
					     PHY_RTL8201_STAT2_AUTO_NEG );
				uiStatus |= uiStatus_bak;

				/* mask out all uninteresting parts */
			}
#elif defined (CONFIG_CC9C)  || (CONFIG_CCW9C)
	unsigned short uiStatus_bak;
			if( phyDetected == PHY_ICS1893BK ) {
				uiStatus = ns9750_mii_read( PHY_COMMON_AUTO_ADV );
				uiStatus &= (PHY_ICS1893_QPSTAT_100BTX);
				uiStatus_bak = uiStatus;
				uiStatus = ns9750_mii_read( PHY_COMMON_CTRL );
				uiStatus &= (PHY_ICS1893_QPSTAT_DUPLEX );
				uiStatus |= uiStatus_bak;

				/* mask out all uninteresting parts */
			}
#else
			if( phyDetected == PHY_LXT971A ) {
				uiStatus = ns9750_mii_read( PHY_LXT971_STAT2 );
				uiStatus &= (PHY_LXT971_STAT2_100BTX |
					     PHY_LXT971_STAT2_DUPLEX_MODE |
					     PHY_LXT971_STAT2_AUTO_NEG );

				/* mask out all uninteresting parts */
			}
#endif
			/* other PHYs must store there link information in
			   uiStatus as PHY_LXT971 */
		}
	} else {
		/* mode has been forced, so uiStatus should be the same as the
		   last link status, enforce printing */
		uiStatus = uiLastLinkStatus;
		uiLastLinkStatus = 0xff;
	}

	if( uiStatus != uiLastLinkStatus ) {
		/* save current link status */
		uiLastLinkStatus = uiStatus;

		/* print new link status */

#ifdef CONFIG_NS9750ACCORD
		printk( KERN_INFO NS9750_DRIVER_NAME
			": link mode %i Mbps %s duplex %s\n",
			(uiStatus & PHY_RTL8201_STAT2_100BTX) ? 100 : 10,
			(uiStatus & PHY_RTL8201_STAT2_DUPLEX_MODE)?"full":"half",
			(uiStatus & PHY_RTL8201_STAT2_AUTO_NEG)?"(auto)":"" );
#elif defined (CONFIG_CC9C) || (CONFIG_CCW9C)
		printk( KERN_INFO NS9750_DRIVER_NAME
			": link mode\n");
#else
		printk( KERN_INFO NS9750_DRIVER_NAME
			": link mode %i Mbps %s duplex %s\n",
			(uiStatus & PHY_LXT971_STAT2_100BTX) ? 100 : 10,
			(uiStatus & PHY_LXT971_STAT2_DUPLEX_MODE)?"full":"half",
			(uiStatus & PHY_LXT971_STAT2_AUTO_NEG)?"(auto)":"" );

#endif
	}
}

/***********************************************************************
 * the MII low level stuff
 ***********************************************************************/

/***********************************************************************
 * @Function: ns9750_mii_identify_phy
 * @Return: 1 if supported PHY has been detected otherwise 0
 * @Descr: checks for supported PHY and prints the IDs.
 ***********************************************************************/

static char ns9750_mii_identify_phy( void )
{
	unsigned short uiID1;
	unsigned short uiID2;
	char* szName;
	char cRes = 0;
        char *szPostAutoNegDelay = NULL;
        
	DEBUG_FN( DEBUG_MII );

	uiID1 = ns9750_mii_read( PHY_COMMON_ID1 );
	phyDetected = (PhyType)uiID1;

        /* env ins in us */
        szPostAutoNegDelay = getenv( "post_auto_negotiation_delay" );
        uiPostAutoNegDelay =
                ( ( NULL != szPostAutoNegDelay) ?
                  ( simple_strtoul( szPostAutoNegDelay, NULL, 10 ) * 1000 )
                  : 0 );

	switch( phyDetected ) {
#ifdef CONFIG_NS9750ACCORD
	    case PHY_RTL8201:
		szName = "RTL8201";
		uiID2 = ns9750_mii_read( PHY_COMMON_ID2 );
		nPhyMaxMdioClock = PHY_RTL8201_MDIO_MAX_CLK;
		cRes = 1;
		break;
#elif defined (CONFIG_CC9C) || (CONFIG_CCW9C)
	    case PHY_ICS1893BK:
		szName = "ICS1893BK";
		uiID2 = ns9750_mii_read( PHY_COMMON_ID2 );
		nPhyMaxMdioClock = PHY_ICS1893_MDIO_MAX_CLK;
		cRes = 1;
		break;
#else
	    case PHY_LXT971A:
		szName = "LXT971A";
		uiID2 = ns9750_mii_read( PHY_COMMON_ID2 );
		nPhyMaxMdioClock = PHY_LXT971_MDIO_MAX_CLK;
		cRes = 1;
		break;
#endif
	    case PHY_NONE:
	    default:
		/* in case uiID1 == 0 && uiID2 == 0 we may have the wrong
		   address or reset sets the wrong NS9750_ETH_MCFG_CLKS */

		uiID2 = 0;
		szName = "unknown";
		nPhyMaxMdioClock = PHY_MDIO_MAX_CLK;
		phyDetected = PHY_NONE;
	}

	/* Adjust the max MDIO clock, reducing the datasheet value, to 
	 * compensate the effect of the spread-spectrum */
	if( nPhyMaxMdioClock != PHY_MDIO_MAX_CLK )
		nPhyMaxMdioClock = 
			( nPhyMaxMdioClock * ( 100 - SPREAD_SPECTRUM_PERCENTAGE ) ) / 100;

	printk( KERN_INFO NS9750_DRIVER_NAME
		": PHY (0x%x, 0x%x) = %s detected\n",
		uiID1,
		uiID2,
		szName );

	return cRes;
}


/***********************************************************************
 * @Function: ns9750_mii_read
 * @Return: the data read from PHY register uiRegister
 * @Descr: the data read may be invalid if timed out. If so, a message
 *         is printed but the invalid data is returned.
 *         The fixed device address is being used.
 ***********************************************************************/

static unsigned short ns9750_mii_read( unsigned short uiRegister )
{
	DEBUG_FN( DEBUG_MII_LOW );

	/* write MII register to be read */
	*get_eth_reg_addr(NS9750_ETH_MADR)=NS9750_ETH_PHY_ADDRESS<<8|uiRegister;

	*get_eth_reg_addr( NS9750_ETH_MCMD ) = NS9750_ETH_MCMD_READ;

	if( !ns9750_mii_poll_busy() )
	    printk( KERN_WARNING NS9750_DRIVER_NAME
		    ": MII still busy in read\n" );
	/* continue to read */

	*get_eth_reg_addr( NS9750_ETH_MCMD ) = 0;

	return (unsigned short) (*get_eth_reg_addr( NS9750_ETH_MRDD ) );
}


/***********************************************************************
 * @Function: ns9750_mii_write
 * @Return: nothing
 * @Descr: writes the data to the PHY register. In case of a timeout,
 *         no special handling is performed but a message printed
 *         The fixed device address is being used.
 ***********************************************************************/

static void ns9750_mii_write( unsigned short uiRegister, unsigned short uiData )
{
	DEBUG_FN( DEBUG_MII_LOW );

	/* write MII register to be written */
	*get_eth_reg_addr( NS9750_ETH_MADR)=NS9750_ETH_PHY_ADDRESS<<8|uiRegister;

	*get_eth_reg_addr( NS9750_ETH_MWTD ) = uiData;

	if( !ns9750_mii_poll_busy() )
		printf( KERN_WARNING NS9750_DRIVER_NAME
			": MII still busy in write\n");
}


/***********************************************************************
 * @Function: ns9750_mii_get_clock_divisor
 * @Return: the clock divisor that should be used in NS9750_ETH_MCFG_CLKS
 * @Descr: if no clock divisor can be calculated for the
 *         current SYSCLK and the maximum MDIO Clock, a warning is printed
 *         and the greatest divisor is taken
 ***********************************************************************/

static unsigned int ns9750_mii_get_clock_divisor( unsigned int unMaxMDIOClk )
{
	struct
	{
		unsigned int unSysClkDivisor;
		unsigned int unClks; /* field for NS9750_ETH_MCFG_CLKS */
	} PHYClockDivisors[] = {
		{  4, NS9750_ETH_MCFG_CLKS_4 },
		{  6, NS9750_ETH_MCFG_CLKS_6 },
		{  8, NS9750_ETH_MCFG_CLKS_8 },
		{ 10, NS9750_ETH_MCFG_CLKS_10 },
		{ 20, NS9750_ETH_MCFG_CLKS_20 },
		{ 30, NS9750_ETH_MCFG_CLKS_30 },
		{ 40, NS9750_ETH_MCFG_CLKS_40 }
	};

	int nIndexSysClkDiv;
	int nArraySize = sizeof(PHYClockDivisors) / sizeof(PHYClockDivisors[0]);
	unsigned int unClks = NS9750_ETH_MCFG_CLKS_40; /* defaults to
							  greatest div */

	DEBUG_FN( DEBUG_INIT );

	for( nIndexSysClkDiv=0; nIndexSysClkDiv < nArraySize;nIndexSysClkDiv++) {
		/* find first sysclock divisor that isn't higher than 2.5 MHz
		   clock */
		if( AHB_CLK_FREQ /
		    PHYClockDivisors[ nIndexSysClkDiv ].unSysClkDivisor <=
		    unMaxMDIOClk ) {
			unClks = PHYClockDivisors[ nIndexSysClkDiv ].unClks;
			break;
		}
	}

	DEBUG_ARGS2( DEBUG_INIT,
		     "Taking MDIO Clock bit mask 0x%0x for max clock %i\n",
		     unClks,
		     unMaxMDIOClk );

	/* return greatest divisor */
	return unClks;
}

/***********************************************************************
 * @Function: ns9750_mii_poll_busy
 * @Return: 0 if timed out otherwise the remaing timeout
 * @Descr: waits until the MII has completed a command or it times out
 *         code may be interrupted by hard interrupts.
 *         It is not checked what happens on multiple actions when
 *         the first is still being busy and we timeout.
 ***********************************************************************/

static unsigned int ns9750_mii_poll_busy( void )
{
	unsigned int unTimeout = 10000;

	DEBUG_FN( DEBUG_MII_LOW );

	while( (( *get_eth_reg_addr( NS9750_ETH_MIND ) & NS9750_ETH_MIND_BUSY)
		== NS9750_ETH_MIND_BUSY ) &&
	       unTimeout )
		unTimeout--;

	return unTimeout;
}

#if (CONFIG_COMMANDS & CFG_CMD_MII)

void mii_init(void)
{
	ns9750_eth_reset();
}
/***********************************************************************
 * @Function: miiphy_read based on ns9750_mii_read
 * @Return: the data read from PHY register reg
 * @Descr: the data read may be invalid if timed out. If so, a message
 *         is printed but the invalid data is returned.
 *         The fixed device address is being used.
 ***********************************************************************/

int miiphy_read( unsigned char addr, unsigned char reg, unsigned short *value )
{
	unsigned long sta_reg;	/* STA scratch area */

	DEBUG_FN( DEBUG_MII_LOW );

	/* write MII register to be read */
	*get_eth_reg_addr(NS9750_ETH_MADR)=NS9750_ETH_PHY_ADDRESS<<8|reg;

	*get_eth_reg_addr( NS9750_ETH_MCMD ) = NS9750_ETH_MCMD_READ;

	if( !ns9750_mii_poll_busy() )
	    printk( KERN_WARNING NS9750_DRIVER_NAME
		    ": MII still busy in read\n" );
	/* continue to read */

	*get_eth_reg_addr( NS9750_ETH_MCMD ) = 0;

	sta_reg = (unsigned short) (*get_eth_reg_addr( NS9750_ETH_MRDD ) );
	*value = *(short *) (&sta_reg);
	return 0;
}


/***********************************************************************
 * @Function: miiphy_write based on ns9750_mii_write
 * @Return: != 0 on error
 * @Descr: writes the data to the PHY register. In case of a timeout,
 *         no special handling is performed but a message printed
 *         The fixed device address is being used.
 ***********************************************************************/

int miiphy_write (unsigned char addr, unsigned char reg, unsigned short value)
{
	DEBUG_FN( DEBUG_MII_LOW );

	/* write MII register to be written */
	*get_eth_reg_addr( NS9750_ETH_MADR)=NS9750_ETH_PHY_ADDRESS<<8|reg;

	*get_eth_reg_addr( NS9750_ETH_MWTD ) = value;

	if( !ns9750_mii_poll_busy() )
		printk( KERN_WARNING NS9750_DRIVER_NAME
			": MII still busy in write\n");
	return 0;
}
#endif	/* CONFIG_COMMANDS & CFG_CMD_MII */

/***********************************************************************
 * @Function: eth_use_mac_from_env
 * @Return: 0 if ok, < 0 on failure
 * @Descr: Stores MAC address in chip
 ***********************************************************************/

int eth_use_mac_from_env( bd_t* pbis )
{
	unsigned char aucMACAddr[ 6 ] = { 0x00,0x04,0xf3,0x00,0x06,0x35 };

	char* pcTmp = getenv( "ethaddr" );
	char* pcEnd;
        int   i;

        ns9750_eth_reset_mac();

	if( pcTmp != NULL ) {
                /* copy MAC address */
                for( i = 0; i < 6; i++ ) {
                        aucMACAddr[ i ] = pcTmp ? simple_strtoul( pcTmp, &pcEnd, 16 ) : 0;
                        /* next char or terminating zero */
                        pcTmp = (*pcTmp) ? ( pcEnd + 1 ) : pcEnd;
                }
        } else
                eprintf( "Couldn't read MAC address from environment, using default\n" );


        /* now set it, so linux can use it */
	*get_eth_reg_addr( NS9750_ETH_SA1 ) = aucMACAddr[ 5 ]<<8 | aucMACAddr[ 4 ];
	*get_eth_reg_addr( NS9750_ETH_SA2 ) = aucMACAddr[ 3 ]<<8 | aucMACAddr[ 2 ];
	*get_eth_reg_addr( NS9750_ETH_SA3 ) = aucMACAddr[ 1 ]<<8 | aucMACAddr[ 0 ];

	return 0;
}

#endif /* CONFIG_DRIVER_NS9750_ETHERNET */
