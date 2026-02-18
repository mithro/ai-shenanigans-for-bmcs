/*
 * Copyright (C) 2006 by FS Forth-Systeme, a DIGI International Company
 * All rights reserved.
 *
 * $Id:
 * @Author: Joachim Jaeger (Joachim_Jaeger@digi.com)
 * @Descr: Driver for internal RTC of NS9360 CPU
 * @References: Code comes from NetOS sources for CC9P9360
 * @TODO:
 *
 * See file CREDITS for list of people who contributed to this
 * project.
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
 */

/*
 * Date & Time support for the built-in Netsilicon NS9360 RTC
 *
 * This RTC device is configured with 24-hour mode.
 * The range of years is from 1900 to 2999.
 *
 * This NS9360 Real Time Clock (RTC) device is added in @link naRtcDeviceTable .
 * Use the device id defined in naRtcDeviceTable to access this NS9360 RTC.
 * NS9360 RTC supports only 1 alarm and the id is 0.
 *
 */

#include <common.h>
#include <command.h>

#if defined(CONFIG_RTC_NS9360) && (CONFIG_COMMANDS & CFG_CMD_DATE)

#if defined(CONFIG_CC9C) || (CONFIG_CCW9C)
# include <ns9360_rtc.h>
#endif

#include <rtc.h>

/*---------------------------------------------------------------------*/
#undef DEBUG_RTC

#ifdef DEBUG_RTC
#define DEBUGR(fmt,args...) printf(fmt ,##args)
#else
#define DEBUGR(fmt,args...)
#endif
/*---------------------------------------------------------------------*/

/* decimal number converts to BCD (2 digits) */
#define DECIMAL_TO_BCD(a)   ((((a & 0xff)/10) << 4) + ((a & 0xff)%10))

static unsigned int  rtc_initialized = _RTC_NOT_INITIALIZED;

/*
 * This function is used to convert the given bcd value to decimal value.
 * It converts the bcd value in the given bits to the decimal value.
 *
 * @param    value              value that contains BCD to be converted into decimal
 * @param    unit_shift         index to the 1st bit of the BCD value
 * @param    hi_mask            number of bits of the tens unit
 *                        
 * @return  "decimal value"     decimal value of the given BCD.
 */
static unsigned long reg_bcd_to_decimal(unsigned int value, unsigned unit_shift, unsigned hi_mask) {
#define BCD_TO_DECIMAL(a)   ((10 * (a >> 4)) + (a & 0xf) )

	unsigned long bcd_value;
	unsigned long ret_value = 0;
    
	/* get the bcd value */
	bcd_value = (value >> unit_shift);
                
	/* mask off the rest of the bits */
	if (hi_mask > 0)
		bcd_value &= ((0x10 << hi_mask) - 1); /* contains tens unit */
	else
		bcd_value &= 0xf;  /* no tens unit */

	ret_value = BCD_TO_DECIMAL(bcd_value);

	return ret_value;
}    

/*
 * Initializes the real time clock. This function enables and sets up the 
 * specified real time clock device.
 *
 */
void rtc_reset (void) {
	
	ulong reg_value;
	
	if ((rtc_initialized & _RTC_TIME_INITIALIZED) == 0) {
		/* enable rtc device */
		*get_sys_reg_addr( NS9750_SYS_CLOCK ) |= NS9750_SYS_CLOCK_RTC;
		/* setup the RTC clock control frequency */
		*get_sys_reg_addr( NS9750_SYS_RTC_CTRL_BASE ) = (CONFIG_SYS_CLK_FREQ/200);

		/* switch to 24h mode */
		*get_rtc_reg_addr( NA_RTC_REG_HOUR_MODE ) &= ~NA_RTC_REG_HOUR_MODE_24H;

		/* writes 1 & 0 to ensure it disables the IRQ */
		*get_rtc_reg_addr( NA_RTC_REG_IRQ_ENABLE ) = NA_RTC_REG_IRQ_ALARM_ALL;
		*get_rtc_reg_addr( NA_RTC_REG_IRQ_ENABLE ) &= ~NA_RTC_REG_IRQ_ALARM_ALL;
            
		/* clear all time in the alarm */
		*get_rtc_reg_addr( NA_RTC_REG_ALARM_ENABLE ) &= ~NA_RTC_REG_ALARM_ALL;
            
		/* enable RTC & Calendar operations */    
		*get_rtc_reg_addr( NA_RTC_REG_GEN_CNTRL ) &= ~NA_RTC_GEN_CNTRL_ON;
		
		/* we initialized all necessary registers */
		rtc_initialized |= _RTC_TIME_INITIALIZED;  
             
		/* Make a read to clear the status in the event register */
		reg_value = *get_rtc_reg_addr( NA_RTC_REG_EVENT_STATUS );
	}
}

/*
 * Sets time to the real time clock device. It writes specified time 
 * into specified real-time clock control.
 *  
 */
void rtc_set (struct rtc_time *tmp) {
    
	ulong reg_value;
	
	if ((rtc_initialized & _RTC_TIME_INITIALIZED) == 0)
		rtc_reset();

	/* Disable RTC & Calendar operations */
	*get_rtc_reg_addr( NA_RTC_REG_GEN_CNTRL ) |= NA_RTC_GEN_CNTRL_ON;
	
	/*********************
	* Update Time
	*********************/  
	reg_value = 0x0;
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_sec)) << SECONDS_BCD_START_BIT_INDEX);
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_min)) << MINUTES_BCD_START_BIT_INDEX);
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_hour)) << HOURS_BCD_START_BIT_INDEX);
	*get_rtc_reg_addr( NA_RTC_REG_TIME_TIME ) = reg_value;
	DEBUGR("RTC_SET: RTC time setting: 0x%x\n",reg_value);
	
	/*********************
	* Update Date
	*********************/ 
	reg_value = 0x0;
	reg_value |= (DECIMAL_TO_BCD(tmp->tm_wday) + 1);
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_mon)) << MONTH_BCD_START_BIT_INDEX);
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_mday)) << DATE_BCD_START_BIT_INDEX);
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_year%100)) << YEAR_BCD_START_BIT_INDEX);
	reg_value |= ((DECIMAL_TO_BCD(tmp->tm_year/100)) << CENTURY_YEAR_BCD_START_BIT_INDEX);
	*get_rtc_reg_addr( NA_RTC_REG_CALENDAR_TIME ) = reg_value;
	DEBUGR("RTC_SET: RTC date setting: 0x%x\n",reg_value);
	
	/* Make sure time and calendar are valid */
	reg_value = *get_rtc_reg_addr( NA_RTC_REG_GEN_STATUS );
	if ((reg_value & NA_RTC_VALID_STATUS) != NA_RTC_VALID_STATUS) {
		/* TODO  */
		printf("RTC_SET: RTC setting failed! Status: 0x%x\n",reg_value);
		rtc_initialized = _RTC_NOT_INITIALIZED;
	}
	
	/* enable RTC & Calendar operations */    
	*get_rtc_reg_addr( NA_RTC_REG_GEN_CNTRL ) &= ~NA_RTC_GEN_CNTRL_ON;
}

/*
 * Gets time from the real time device. 
 * It reads the time from specified real time control.
 * 
 */
void rtc_get (struct rtc_time *tmp)
{
	ulong reg_value;
	
	if ((rtc_initialized & _RTC_TIME_INITIALIZED) == 0)
		rtc_reset();

	/*
	* Hours, minutes, and seconds are in binary coded decimal.
	*/
	reg_value = *get_rtc_reg_addr( NA_RTC_REG_TIME_TIME );
	
	tmp->tm_sec = reg_bcd_to_decimal(reg_value, SECONDS_BCD_START_BIT_INDEX, SECONDS_BCD_TENS_UNIT);
	tmp->tm_min = reg_bcd_to_decimal(reg_value, MINUTES_BCD_START_BIT_INDEX, MINUTES_BCD_TENS_UNIT);
	tmp->tm_hour = reg_bcd_to_decimal(reg_value, HOURS_BCD_START_BIT_INDEX, HOURS_BCD_TENS_UNIT);

	/*
	* Date, month, and year are binary coded decimal.  Year is only two digits.
	*/
	reg_value = *get_rtc_reg_addr( NA_RTC_REG_CALENDAR_TIME );

	tmp->tm_wday = (reg_value & DAYWEEK_BCD_START_BIT_MASK) - 1;
	tmp->tm_mon = reg_bcd_to_decimal(reg_value, MONTH_BCD_START_BIT_INDEX, MONTH_BCD_TENS_UNIT);
	tmp->tm_mday = reg_bcd_to_decimal(reg_value, DATE_BCD_START_BIT_INDEX, DATE_BCD_TENS_UNIT);
	tmp->tm_year = reg_bcd_to_decimal(reg_value, YEAR_BCD_START_BIT_INDEX, YEAR_BCD_TENS_UNIT);
	tmp->tm_year += (reg_bcd_to_decimal(reg_value, CENTURY_YEAR_BCD_START_BIT_INDEX, 
						CENTURY_YEAR_BCD_TENS_UNIT) * 100); 

	DEBUGR ("Get DATE: %4d-%02d-%02d (wday=%d)  TIME: %2d:%02d:%02d\n",
		tmp->tm_year, tmp->tm_mon, tmp->tm_mday, tmp->tm_wday,
		tmp->tm_hour, tmp->tm_min, tmp->tm_sec);
	
}

#endif	/* CONFIG_RTC_NS9360 && CFG_CMD_DATE */
