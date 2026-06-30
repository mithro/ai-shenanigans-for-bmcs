/***********************************************************************
 *
 * Copyright (C) 2006 by FS Forth-Systeme, a DIGI International Company
 * All rights reserved.
 *
 * $Id: ns9360_rtc.h,v 1.1 2006-08-25 10:06:45 jjaeger Exp $
 * @Author: Joachim Jaeger
 * @References: [1] NS9360 Hardware Reference, December 2005, Chap. 10
 * 		[2] Derives from NetOS code
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

#ifndef FS_NS9360_RTC_H
#define FS_NS9360_RTC_H

#define	NS9360_RTC_MODULE_BASE	 	(0x90700000) /* physical address */

#define get_rtc_reg_addr(c) \
     ((volatile unsigned int*) ( NS9360_RTC_MODULE_BASE+(unsigned int) (c)))


#define NA_RTC_DISABLE			0
#define NA_RTC_ENABLE			1

#define NA_RTC_VALID_STATUS		(0x0000000F)

#define NA_RTC_NUMBER_ALARMS		1       /* number of alarm RTC has */

/* register offsets */
#define NA_RTC_REG_GEN_CNTRL		(0x0000)
#define NA_RTC_REG_HOUR_MODE		(0x0004)
#define NA_RTC_REG_TIME_TIME		(0x0008)
#define NA_RTC_REG_TIME_ALARM		(0x0010)
#define NA_RTC_REG_CALENDAR_TIME	(0x000C)
#define NA_RTC_REG_CALENDAR_ALARM	(0x0014)
#define NA_RTC_REG_ALARM_ENABLE		(0x0018)
#define NA_RTC_REG_EVENT_STATUS		(0x001C)
#define NA_RTC_REG_IRQ_ENABLE		(0x0020)
#define NA_RTC_REG_IRQ_DISABLE		(0x0024)
#define NA_RTC_REG_IRQ_STATUS		(0x0028)
#define NA_RTC_REG_GEN_STATUS		(0x002C)

/* register bit fields */
#define NA_RTC_GEN_CNTRL_ON		(0x00000003)
#define NA_RTC_REG_HOUR_MODE_24H	(0x00000001)
#define NA_RTC_REG_IRQ_ALARM_ALL	(0x0000007F)
#define NA_RTC_REG_ALARM_ALL		(0x0000003F)
#define NA_RTC_REG_EVENT_ALL		(0x0000007F)


/* The following definitions are RTC register bit assignment */
#define SECONDS_BCD_START_BIT_INDEX	8 /* 1st bit of seconds */
#define SECONDS_BCD_TENS_UNIT		3 /* number of bits for tens unit BCD of second */

#define MINUTES_BCD_START_BIT_INDEX	16 /* 1st bit of minutes */
#define MINUTES_BCD_TENS_UNIT		3 /* number of bits for tens unit BCD of minute */

#define HOURS_BCD_START_BIT_INDEX	24 /* 1st bit of hours */
#define HOURS_BCD_TENS_UNIT		2 /* number of bits for tens unit BCD of hour */

#define MONTH_BCD_START_BIT_INDEX	3 /* 1st bit of month */
#define MONTH_BCD_TENS_UNIT		1 /* number of bits for tens unit BCD of month */

#define DATE_BCD_START_BIT_INDEX	8 /* 1st bit of date */
#define DATE_BCD_TENS_UNIT		2 /* number of bits for tens unit BCD of date */

#define YEAR_BCD_START_BIT_INDEX	16 /* 1st bit of year */
#define YEAR_BCD_TENS_UNIT		4 /* number of bits for tens unit BCD of year */

#define CENTURY_YEAR_BCD_START_BIT_INDEX	24 /* 1st bit of century-year */
#define CENTURY_YEAR_BCD_TENS_UNIT		2 /* number of bits for tens unit BCD of century of year */

#define DAYWEEK_BCD_START_BIT_MASK	0x7 /* bit mask of days-of-week */


#define _RTC_NOT_INITIALIZED		0x00	/* RTC device is not initialized */
#define _RTC_TIME_INITIALIZED		0x01	/* RTC device is initialized */


#endif /* FS_NS9360_RTC_H */
