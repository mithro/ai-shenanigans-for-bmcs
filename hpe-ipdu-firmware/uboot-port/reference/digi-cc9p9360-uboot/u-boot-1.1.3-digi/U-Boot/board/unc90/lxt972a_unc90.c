/***********************************************************************
 *
 * Copyright (C) 2005 by Sistemas Embebidos S.A.
 * All rights reserved.
 *
 * $Id: lxt972a_unc90.c,v 1.1 2005-09-15 11:48:46 pperez Exp $
 * @Author: Pedro Perez de Heredia & Neil Bryan
 * @Descr: Phy routines for the at91rm9200_ether.c driver. 
 * @References: [1] A91RM9200 Datasheet, Rev. 1768B-ATARM, 22/Aug/2003
 *		[2] Intel LXT971 Datasheet #249414 Rev. 02
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as
 * published by the Free Software Foundation; either version 2 of
 * the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston,
 * MA 02111-1307 USA
 *
 ***********************************************************************/

#include <at91rm9200_net.h>
#include <net.h>
#include <lxt971a.h>
#if defined(CONFIG_STATUS_LED)
# include <status_led.h>
#endif

#ifdef CONFIG_DRIVER_ETHER

#if (CONFIG_COMMANDS & CFG_CMD_NET)

#define LXT971A_MII_NEG_DELAY		(5*CFG_HZ)
#define LINK_MASK			0x7
#define LINK_SPEED_MASK			0x1
#define LINK_SPEED_10			0x0
#define LINK_SPEED_100			0x1
#define LINK_DUPLEX_MASK		0x2
#define LINK_DUPLEX_HALF		0x0
#define LINK_DUPLEX_FULL		0x2
#define LINK_AUTONEG_ENABLE_MASK	0x4
#define LINK_AUTONEG_DISABLE		0x0
#define LINK_AUTONEG_ENABLE		0x4



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
		printf("%s: " a0, __FUNCTION__ )
# define DEBUG_ARGS1( FLG, a0, a1 ) if( ( nDebugLvl & (FLG) ) == (FLG)) \
		printf("%s: " a0, __FUNCTION__, (int)(a1), 0, 0, 0, 0, 0 )
# define DEBUG_ARGS2( FLG, a0, a1, a2 ) if( (nDebugLvl & (FLG)) ==(FLG))\
		printf("%s: " a0, __FUNCTION__, (int)(a1), (int)(a2) )
# define DEBUG_ARGS3( FLG, a0, a1, a2, a3 ) if((nDebugLvl &(FLG))==(FLG))\
		printf("%s: "a0,__FUNCTION__,(int)(a1),(int)(a2),(int)(a3),0,0,0)
# define DEBUG_FN( FLG ) if( (nDebugLvl & (FLG)) == (FLG) ) \
		printf("\r%s:line %d\n", __FUNCTION__, __LINE__);
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

typedef enum
{
	PHY_NONE    = 0x0000, /* no PHY detected yet */
	PHY_LXT971A = 0x0013
} PhyType;

 
/***********************************************************************
 * @Function: lxt972a_IsPhyConnected
 * @Return: TRUE if ID read successfully, FALSE otherwise.
 * @Descr: Reads the 2 PHY ID registers and compares it with the LX972a
 *         ID.
 ***********************************************************************/
static unsigned int lxt972a_IsPhyConnected( AT91PS_EMAC p_mac ) 
{
	unsigned short Id1, Id2;
	
	DEBUG_FN( DEBUG_INIT );
	
	// Initial delay due to the PWDOWN line has been set to 0...
	udelay( 400 );

	at91rm9200_EmacEnableMDIO( p_mac );
	at91rm9200_EmacReadPhy( p_mac, PHY_COMMON_ID1, &Id1 );
	at91rm9200_EmacReadPhy( p_mac, PHY_COMMON_ID2, &Id2 );
	at91rm9200_EmacDisableMDIO( p_mac );
	
	DEBUG_ARGS2( DEBUG_MII, "PHY IDs = ID1:0x%04x, ID2:0x%04x\n", Id1, Id2 );

	if( PHY_LXT971A == Id1 )
		return TRUE;

	return FALSE;
}

/***********************************************************************
 * @Function: lxt972a_GetLinkSpeed
 * @Return: TRUE if link status set successfully, FALSE otherwise.
 * @Descr: Link parallel detection status of MAC is checked and set into
 *         the MAC configuration registers.
 ***********************************************************************/
static UCHAR lxt972a_GetLinkSpeed( AT91PS_EMAC p_mac )
{
	unsigned short com_control_reg;
	unsigned short com_status_reg_1;
	unsigned short auto_neg_lpba_reg;
   
	DEBUG_FN( DEBUG_INIT );
	
	/* Link status is latched, so read twice to get current value */
	at91rm9200_EmacReadPhy (p_mac, PHY_COMMON_STAT, &com_status_reg_1);
	at91rm9200_EmacReadPhy (p_mac, PHY_COMMON_STAT, &com_status_reg_1);

	/* link status up? */
	if( !(com_status_reg_1 & PHY_COMMON_STAT_LNK_STAT) )
		return FALSE;

	/* Cache Control Register contents */
	at91rm9200_EmacReadPhy (p_mac, PHY_COMMON_CTRL, &com_control_reg);

	/* Check if auto-negotitation enabled */
	if( PHY_COMMON_CTRL_AUTO_NEG == com_control_reg ) {
		/* Are we in the middle of an auto-negotitation? */
		if( PHY_COMMON_STAT_AN_COMP != com_status_reg_1 )
			return FALSE;
	}

	/* Cache Auto-Negotitation Link Partner Base Page Ability register */
	at91rm9200_EmacReadPhy (p_mac, PHY_COMMON_AUTO_LNKB, &auto_neg_lpba_reg );
   
	/* Test the link ability */
	if( (PHY_COMMON_AUTO_LNKB_100BTXFD == auto_neg_lpba_reg) || 
	    (PHY_COMMON_AUTO_LNKB_100BTX == auto_neg_lpba_reg) ) {
		/* Set EMAC for 100BaseTX. Speed bit: 1 = 100MHz, 0 = 10MHz */
		p_mac->EMAC_CFG |= AT91C_EMAC_SPD;
	}

	if( (PHY_COMMON_AUTO_LNKB_10BTFD == auto_neg_lpba_reg ) || 
	    (PHY_COMMON_AUTO_LNKB_10BT == auto_neg_lpba_reg ) ) {
		/* Set EMAC for 10BaseTX. Speed bit: 1 = 100MHz, 0 = 10MHz */
		p_mac->EMAC_CFG = (p_mac->EMAC_CFG & ~AT91C_EMAC_SPD);
	}

	if ((PHY_COMMON_AUTO_ADV_100BTXFD & auto_neg_lpba_reg ) ||
	    (PHY_COMMON_AUTO_LNKB_10BTFD & auto_neg_lpba_reg ) ) {
		/*set EMAC for Full-Duplex  */
		p_mac->EMAC_CFG = (p_mac->EMAC_CFG | AT91C_EMAC_FD);
	} else {
		/*set EMAC for Half-Duplex  */
		p_mac->EMAC_CFG = (p_mac->EMAC_CFG & ~AT91C_EMAC_FD);
	}
 
	return TRUE;

}

/***********************************************************************
 * @Function: lxt972a_InitPhy
 * @Return: TRUE if link status set successfully, FALSE otherwise.
 * @Descr: Initialization routines of the PHY.
 ***********************************************************************/
static UCHAR lxt972a_getLinkMode( void )
{
	char *data;
	char *colon;
	unsigned char link_mode = 0;
	   
	DEBUG_FN( DEBUG_INIT );

	// Get link environment information
	if( ( data = getenv( "link" ) ) != NULL ) {
		
		DEBUG_ARGS1( DEBUG_LINK, "Link Mode = %s\n", data );
	
		if( !strcmp( data, "auto" ) ) {
			link_mode = LINK_AUTONEG_ENABLE;
		} else if( ( colon = strchr( data, ':' ) ) != NULL ) {
			if( !strcmp( colon + 1, "half" ) )
				link_mode = LINK_DUPLEX_HALF; 
			else if( !strcmp( colon + 1, "full" ) )
				link_mode = LINK_DUPLEX_FULL; 
		
			if( NULL != strstr( data, "100" ) )
				link_mode |= LINK_SPEED_100;
			else if( NULL != strstr( data, "10" ) )
				link_mode |= LINK_SPEED_10;
		}
	} else {
		// If link env var is not defined, autonegotiate
		// by default
		link_mode = LINK_AUTONEG_ENABLE;
	}
	
	return link_mode;
}

/***********************************************************************
 * @Function: lxt972a_LinkForce
 * @Return: Nothing.
 * @Descr: Configures the MII link mode as defined in link var.
 ***********************************************************************/
static void lxt972a_LinkForce( AT91PS_EMAC p_mac, unsigned char link )
{
	unsigned short value;
	unsigned int emac_cfg;
	
	DEBUG_FN( DEBUG_LINK );

	at91rm9200_EmacEnableMDIO( p_mac );

	at91rm9200_EmacReadPhy( p_mac, PHY_COMMON_CTRL, &value );
	
	value &= ~( PHY_COMMON_CTRL_SPD_MA | PHY_COMMON_CTRL_AUTO_NEG |
	            PHY_COMMON_CTRL_DUPLEX );

	emac_cfg = p_mac->EMAC_CFG & ~(AT91C_EMAC_SPD | AT91C_EMAC_FD);
	
	if( ( link & LINK_SPEED_MASK ) == LINK_SPEED_100 ) {
	    value |= PHY_COMMON_CTRL_SPD_100;
	    emac_cfg |= AT91C_EMAC_SPD;
	} else {
	    value |= PHY_COMMON_CTRL_SPD_10;
	}

	if( ( link & LINK_DUPLEX_MASK ) == LINK_DUPLEX_FULL ) {
	    value |= PHY_COMMON_CTRL_DUPLEX;
	    emac_cfg |= AT91C_EMAC_FD;
	}
	
	at91rm9200_EmacWritePhy( p_mac, PHY_COMMON_CTRL, &value );
	
	/* Set new configuration */
	p_mac->EMAC_CFG = emac_cfg;
		
	at91rm9200_EmacDisableMDIO( p_mac );
}

/***********************************************************************
 * @Function: lxt972a_AutoNegotiate
 * @Return: TRUE if link status is successfully set, FALSE otherwise.
 * @Descr: Initialises the interface functions to the PHY.
 ***********************************************************************/
static UCHAR lxt972a_AutoNegotiate (AT91PS_EMAC p_mac, int *status)
{
	unsigned short value;
	unsigned short PhyAnar;
	unsigned short PhyAnalpar;
	unsigned short auto_stat;
	unsigned int jiffies_start;
   
	DEBUG_FN( DEBUG_LINK );
	
	at91rm9200_EmacEnableMDIO (p_mac);

	/* Set the Auto_negotiation Advertisement Register */
	/* MII advertising for Next page, 100BaseTxFD and HD, 10BaseTFD and HD, IEEE 802.3 */
	PhyAnar = PHY_COMMON_AUTO_ADV_100BTXFD | 
		PHY_COMMON_AUTO_ADV_100BTX | PHY_COMMON_AUTO_ADV_10BTFD | 
		PHY_COMMON_AUTO_ADV_10BT | PHY_COMMON_AUTO_ADV_802_3;
   
	at91rm9200_EmacWritePhy( p_mac, PHY_COMMON_AUTO_ADV, &PhyAnar );
   
	at91rm9200_EmacReadPhy( p_mac, PHY_COMMON_CTRL, &value );

	value = PHY_COMMON_CTRL_AUTO_NEG | PHY_COMMON_CTRL_RES_AUTO;
	    
	at91rm9200_EmacWritePhy( p_mac, PHY_COMMON_CTRL, &value );

	/* wait for completion */
	jiffies_start = get_ticks ();
	while (get_ticks () < jiffies_start + LXT971A_MII_NEG_DELAY) {
	
		at91rm9200_EmacReadPhy( p_mac, PHY_COMMON_STAT, &auto_stat );
		if ((auto_stat &
		     (PHY_COMMON_STAT_AN_COMP | PHY_COMMON_STAT_LNK_STAT)) ==
		     (PHY_COMMON_STAT_AN_COMP | PHY_COMMON_STAT_LNK_STAT)) 
		{
			DEBUG_ARGS0( DEBUG_LINK, "Auto-negotiation succeeded\n" );
			break;
		}
	}

	at91rm9200_EmacReadPhy (p_mac, PHY_COMMON_STAT, &value);
   
	if( !(value & PHY_COMMON_STAT_AN_COMP) )
		goto error_autoneg;	// Horrible... (sorry)
   
	/* Get the AutoNeg Link partner base page */
	at91rm9200_EmacReadPhy( p_mac, PHY_COMMON_AUTO_LNKB, &PhyAnalpar );

	if( (PhyAnar & PHY_COMMON_AUTO_ADV_100BTXFD ) && 
	    (PhyAnalpar & PHY_COMMON_AUTO_LNKB_100BTXFD) ) 
	{
		/*set MII for 100BaseTX and Full Duplex  */
		p_mac->EMAC_CFG |= AT91C_EMAC_SPD | AT91C_EMAC_FD;
		DEBUG_ARGS0( DEBUG_LINK, "Link mode: 100 Mbps, Full-Duplex\n" );
		goto success_autoneg;
	}

	if( (PhyAnar & PHY_COMMON_AUTO_ADV_10BTFD) && 
	    (PhyAnalpar & PHY_COMMON_AUTO_LNKB_10BTFD) ) 
	{
		/*set MII for 10BaseT and Full Duplex  */
		p_mac->EMAC_CFG = (p_mac->EMAC_CFG &
			~(AT91C_EMAC_SPD | AT91C_EMAC_FD)) | AT91C_EMAC_FD;
		DEBUG_ARGS0( DEBUG_LINK, "Link mode: 10 Mbps, Full-Duplex\n" );
		goto success_autoneg;
	}

error_autoneg:   
	at91rm9200_EmacDisableMDIO( p_mac );
	return FALSE;
	
success_autoneg:
	at91rm9200_EmacDisableMDIO( p_mac );
	return TRUE;
}

/***********************************************************************
 * @Function: lxt972a_InitPhy
 * @Return: TRUE if link status set successfully, FALSE otherwise.
 * @Descr: Initialization routines of the PHY.
 ***********************************************************************/
static UCHAR lxt972a_InitPhy( AT91PS_EMAC p_mac )
{
	UCHAR ret = TRUE;
	unsigned short phy_reg;
	unsigned short usLed;
	unsigned char link;
	
	DEBUG_FN( DEBUG_INIT );

	at91rm9200_EmacEnableMDIO( p_mac );

	/* @TODO Reset the PHY here? */
	/* @TODO check time */
	udelay( 3000 );		/* [2] p.70 says at least 300us reset recovery time. But
				   go sure, it didn't worked stable at higher timer
				   frequencies under LxNETES-2.x */

	/* Disable PHY Interrupts */
	at91rm9200_EmacReadPhy( p_mac, PHY_LXT971_INT_STATUS, &phy_reg );

	/* Set LED2 to display link && activity */
	usLed = PHY_LXT971_LED_CFG_LINK_ACT << PHY_LXT971_LED_CFG_SHIFT_LED2;   
	at91rm9200_EmacWritePhy( p_mac, PHY_LXT971_LED_CFG, &usLed );

	/* clear FDX, SPD, Link, INTR masks */
	phy_reg &= ~( PHY_LXT971_INT_ENABLE_DUPLEXMSK |
		      PHY_LXT971_INT_ENABLE_SPEEDMSK |
		      PHY_LXT971_INT_ENABLE_LINKMSK |
		      PHY_LXT971_INT_ENABLE_INTEN );

	at91rm9200_EmacWritePhy( p_mac, PHY_LXT971_INT_ENABLE, &phy_reg );

	at91rm9200_EmacDisableMDIO( p_mac );
	
	link = lxt972a_getLinkMode();

	if( ( link & LINK_AUTONEG_ENABLE_MASK ) == LINK_AUTONEG_ENABLE ) {
		ret = lxt972a_AutoNegotiate( p_mac, NULL );
	} else {
		lxt972a_LinkForce( p_mac, link );
	}
	
	return( ret );
}

/***********************************************************************
 * @Function: at91rm92000_GetPhyInterface
 * @Return: Nothing.
 * @Descr: Initialises the interface functions to the PHY.
 ***********************************************************************/
void at91rm92000_GetPhyInterface( AT91PS_PhyOps p_phyops )
{
	DEBUG_FN( DEBUG_INIT );

	p_phyops->Init = lxt972a_InitPhy;
	p_phyops->IsPhyConnected = lxt972a_IsPhyConnected;
	p_phyops->GetLinkSpeed = lxt972a_GetLinkSpeed;
	p_phyops->AutoNegotiate = lxt972a_AutoNegotiate;
}

#endif	/* CONFIG_COMMANDS & CFG_CMD_NET */

#endif	/* CONFIG_DRIVER_ETHER */
