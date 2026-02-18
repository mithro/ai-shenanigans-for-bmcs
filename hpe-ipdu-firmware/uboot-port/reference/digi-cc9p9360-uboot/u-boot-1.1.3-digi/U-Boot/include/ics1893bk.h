/***********************************************************************
 *
 * Copyright (C) 2005 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: ics1893bk.h,v 1.1 2005-09-13 13:17:57 jdietsch Exp $
 * @Author: Jonas Dietsche
 * @References: 
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

#ifndef __ICS1893BK_H__
#define __ICS1893BK_H__

/* PHY definitions ICS1893BK */
#define PHY_COMMON_CTRL			(0x00)
#define PHY_COMMON_STAT			(0x01)
#define PHY_COMMON_ID1			(0x02)
#define PHY_COMMON_ID2			(0x03)
#define PHY_COMMON_AUTO_ADV	(0x04)
#define PHY_COMMON_AUTO_LNKB	(0x05)
#define PHY_COMMON_AUTO_EXP	(0x06)
#define PHY_COMMON_AUTO_NEXT	(0x07)
#define PHY_COMMON_AUTO_LNKN	(0x08)
#define PHY_ICS1893_EXT_CTRL		(0x10)
#define PHY_ICS1893_QPSTAT		(0x11)
#define PHY_ICS1893_10B_OPSTAT	(0x12)
#define PHY_ICS1893_EXT_CTRL_2	(0x13)

/* CTRL PHY Control Register Bit Fields */
#define PHY_COMMON_CTRL_RESET		(0x8000)
#define PHY_COMMON_CTRL_LOOPBACK	(0x4000)
#define PHY_COMMON_CTRL_SPD_MA   	(0x2000)
#define PHY_COMMON_CTRL_SPD_10		(0x0000)
#define PHY_COMMON_CTRL_SPD_100		(0x2000)
#define PHY_COMMON_CTRL_AUTO_NEG	(0x1000)
#define PHY_COMMON_CTRL_POWER_DN	(0x0800)
#define PHY_COMMON_CTRL_ISOLATE	 	(0x0400)
#define PHY_COMMON_CTRL_RES_AUTO	(0x0200)
#define PHY_COMMON_CTRL_DUPLEX	 	(0x0100)
#define PHY_COMMON_CTRL_COL_TEST	(0x0080)
#define PHY_COMMON_CTRL_RES1		(0x003F)

/* STAT Status Register Bit Fields */
#define PHY_COMMON_STAT_100BT4	 	(0x8000)
#define PHY_COMMON_STAT_100BXFD	 	(0x4000)
#define PHY_COMMON_STAT_100BXHD	(0x2000)
#define PHY_COMMON_STAT_10BTFD		(0x1000)
#define PHY_COMMON_STAT_10BTHD		(0x0800)
#define PHY_COMMON_STAT_MF_PSUP		(0x0040)
#define PHY_COMMON_STAT_AN_COMP	(0x0020)
#define PHY_COMMON_STAT_RMT_FLT		(0x0010)
#define PHY_COMMON_STAT_AN_CAP		(0x0008)
#define PHY_COMMON_STAT_LNK_STAT	(0x0004)
#define PHY_COMMON_STAT_JAB_DTCT	(0x0002)
#define PHY_COMMON_STAT_EXT_CAP		(0x0001)

/* AUTO_ADV Auto-neg Advert Register Bit Fields */
#define PHY_COMMON_AUTO_ADV_NP			(0x8000)
#define PHY_COMMON_AUTO_ADV_RES1		(0x4000)
#define PHY_COMMON_AUTO_ADV_RMT_FLT	(0x2000)
#define PHY_COMMON_AUTO_ADV_RES2		(0x1000)
#define PHY_COMMON_AUTO_ADV_RES3		(0x0800)
#define PHY_COMMON_AUTO_ADV_RES4		(0x0400)
#define PHY_COMMON_AUTO_ADV_100BT4		(0x0200)
#define PHY_COMMON_AUTO_ADV_100BTXFD	(0x0100)
#define PHY_COMMON_AUTO_ADV_100BTX		(0x0080)
#define PHY_COMMON_AUTO_ADV_10BTFD		(0x0040)
#define PHY_COMMON_AUTO_ADV_10BT		(0x0020)
#define PHY_COMMON_AUTO_ADV_SEL_FLD_MA	(0x001F)
#define PHY_COMMON_AUTO_ADV_802_3		(0x0001)

/* AUTO_LNKB Auto-neg Link Ability Register Bit Fields */
#define PHY_COMMON_AUTO_LNKB_NP		(0x8000)
#define PHY_COMMON_AUTO_LNKB_ACK		(0x4000)
#define PHY_COMMON_AUTO_LNKB_RMT_FLT	(0x2000)
#define PHY_COMMON_AUTO_LNKB_RES2		(0x1000)
#define PHY_COMMON_AUTO_LNKB_RES3		(0x0800)
#define PHY_COMMON_AUTO_LNKB_RES4		(0x0400)
#define PHY_COMMON_AUTO_LNKB_100BT4	(0x0200)
#define PHY_COMMON_AUTO_LNKB_100BTXFD	(0x0100)
#define PHY_COMMON_AUTO_LNKB_100BTX	(0x0080)
#define PHY_COMMON_AUTO_LNKB_10BTFD	(0x0040)
#define PHY_COMMON_AUTO_LNKB_10BT		(0x0020)
#define PHY_COMMON_AUTO_LNKB_SEL_FLD_MA	(0x001F)
#define PHY_COMMON_AUTO_LNKB_802_3		(0x0001)

/* AUTO_EXP Auto-neg Expansion Register Bit Fields */
#define PHY_COMMON_AUTO_EXP_RES1		(0xFFC0)
#define PHY_COMMON_AUTO_EXP_BASE_PAGE	(0x0020)
#define PHY_COMMON_AUTO_EXP_PAR_DT_FLT	(0x0010)
#define PHY_COMMON_AUTO_EXP_LNK_NP_CAP	(0x0008)
#define PHY_COMMON_AUTO_EXP_NP_CAP		(0x0004)
#define PHY_COMMON_AUTO_EXP_PAGE_REC	(0x0002)
#define PHY_COMMON_AUTO_EXP_LNK_AN_CAP	(0x0001)

/* AUTO_NEXT Aut-neg Next Page Tx Register Bit Fields */
#define PHY_COMMON_AUTO_NEXT_NP		(0x8000)
#define PHY_COMMON_AUTO_NEXT_RES1		(0x4000)
#define PHY_COMMON_AUTO_NEXT_MSG_PAGE	(0x2000)
#define PHY_COMMON_AUTO_NEXT_ACK_2		(0x1000)
#define PHY_COMMON_AUTO_NEXT_TOGGLE	(0x0800)
#define PHY_COMMON_AUTO_NEXT_MSG		(0x07FF)

/* AUTO_LNKN Auto-neg Link Partner Rx Reg Bit Fields */
#define PHY_COMMON_AUTO_LNKN_NP         (0x8000)
#define PHY_COMMON_AUTO_LNKN_RES1        (0x4000)
#define PHY_COMMON_AUTO_LNKN_MSG_PAGE   (0x2000)
#define PHY_COMMON_AUTO_LNKN_ACK_2      (0x1000)
#define PHY_COMMON_AUTO_LNKN_TOGGLE     (0x0800)
#define PHY_COMMON_AUTO_LNKN_MSG        (0x07FF)

/* Extended Control Register */
#define PHY_ICS1893_EXT_CTRL_CMD_OWR		(0x8000)
#define PHY_ICS1893_EXT_CTRL_MONDL_4		(0x0400)
#define PHY_ICS1893_EXT_CTRL_MONDL_3		(0x0200)
#define PHY_ICS1893_EXT_CTRL_MONDL_2		(0x0100)
#define PHY_ICS1893_EXT_CTRL_MONDL_1		(0x0080)
#define PHY_ICS1893_EXT_CTRL_MONDL_0		(0x0040)
#define PHY_ICS1893_EXT_CTRL_MONDL		(0x07C0)
#define PHY_ICS1893_EXT_CTRL_SCIPHER_TEST	(0x0020)
#define PHY_ICS1893_EXT_CTRL_ICS_RES2		(0x0010)
#define PHY_ICS1893_EXT_CTRL_NRZ_NRZI		(0x0008)
#define PHY_ICS1893_EXT_CTRL_TX_INV		(0x0004)
#define PHY_ICS1893_EXT_CTRL_ICS_RES1		(0x0002)
#define PHY_ICS1893_EXT_CTRL_SCIPHER		(0x0001)

/* QuickPoll Detailed Status Register */
#define PHY_ICS1893_QPSTAT_DATA_RATE			(0x8000)
#define PHY_ICS1893_QPSTAT_DUPLEX			(0x4000)
#define PHY_ICS1893_QPSTAT_AUTO_NEG_PROG_2	(0x2000)
#define PHY_ICS1893_QPSTAT_AUTO_NEG_PROG_1	(0x1000)
#define PHY_ICS1893_QPSTAT_AUTO_NEG_PROG_0	(0x0800)
#define PHY_ICS1893_QPSTAT_AUTO_NEG_PROG		(0x3800)
#define PHY_ICS1893_QPSTAT_100TX_LOST			(0x0400)
#define PHY_ICS1893_QPSTAT_100PLL_LOCK 		(0x0200)
#define PHY_ICS1893_QPSTAT_FALSE_CAR_DETECT   	(0x0100)
#define PHY_ICS1893_QPSTAT_INV_DETECT			(0x0080)
#define PHY_ICS1893_QPSTAT_HALT_DETECT		(0x0040)
#define PHY_ICS1893_QPSTAT_PRE_END_DETECT 	(0x0020)
#define PHY_ICS1893_QPSTAT_AUTO_NEG_COMP   	(0x0010)
#define PHY_ICS1893_QPSTAT_100BTX			(0x0008)
#define PHY_ICS1893_QPSTAT_JDETECT  			(0x0004)
#define PHY_ICS1893_QPSTAT_REMFAULT  			(0x0002)
#define PHY_ICS1893_QPSTAT_LINKSTAT   			(0x0001)

/* I10Base-T Operations Register */
#define PHY_ICS1893_10B_OPSTAT_REM_JAB_DTCT		(0x8000)
#define PHY_ICS1893_10B_OPSTAT_POL_RES			(0x4000)
#define PHY_ICS1893_10B_OPSTAT_JAB_INHIB			(0x0020)
#define PHY_ICS1893_10B_OPSTAT_AUTOPOL_INHIB		(0x0008)
#define PHY_ICS1893_10B_OPSTAT_SQE_INHIB			(0x0004)
#define PHY_ICS1893_10B_OPSTAT_LLOSS_INHIB		(0x0002)
#define PHY_ICS1893_10B_OPSTAT_SQUELCH_INHIB		(0x0001)

/* Extended Control Register 2 */
#define PHY_ICS1893_EXT_CTRL_2_RES1      (0xFF00)
#define PHY_ICS1893_EXT_CTRL_2_NODE_MODE			(0x8000)
#define PHY_ICS1893_EXT_CTRL_2_HW_SW_MODE		(0x4000)
#define PHY_ICS1893_EXT_CTRL_2_REM_FAULT			(0x2000)
#define PHY_ICS1893_EXT_CTRL_2_AMDIX_EN			(0x0200)
#define PHY_ICS1893_EXT_CTRL_2_MDI_MODE			(0x0100)
#define PHY_ICS1893_EXT_CTRL_2_TP_TRISTATE			(0x0080)
#define PHY_ICS1893_EXT_CTRL_2_AUTO_100BTX_DWN	(0x0001)

#define PHY_ICS1893_MDIO_MAX_CLK		(25000000)
#define PHY_MDIO_MAX_CLK				(25000000)


#endif /* __ICS1893BK_H__ */
