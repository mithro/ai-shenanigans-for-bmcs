/***********************************************************************
 *
 * Copyright (C) 2004 by FS Forth-Systeme GmbH.
 * All rights reserved.
 *
 * $Id: status_led.h,v 1.2 2005-09-15 11:31:23 pperez Exp $
 * @Author: Joachim Jaeger jjaeger@fsforth.de
 * @Descr: SMDK2410 based status led support functions
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
 */

#ifndef __ASM_STATUS_LED_H__
#define __ASM_STATUS_LED_H__

/* if not overriden */
#ifndef CONFIG_BOARD_SPECIFIC_LED
#ifdef CONFIG_SMDK2410_LED
#include <s3c2410.h>

#elif CONFIG_CC9C_LED
# include <ns9750_bbus.h>

#elif  CONFIG_UNC90

#include <asm/arch/AT91RM9200.h>
#include <configs/unc90.h>
#define	PIO_REG(port,reg)	AT91C_PIO ## port ## reg

#if defined( CONFIG_UNC90_USE_A6_LED )
  #define	PIO_MASK	AT91C_PIO_PD25
  #define	PIO_CODR	PIO_REG(D,_CODR)
  #define	PIO_SODR	PIO_REG(D,_SODR)	
  #define	PIO_ODSR	PIO_REG(D,_ODSR)
  #define	PIO_PER		PIO_REG(D,_PER)
  #define	PIO_OER		PIO_REG(D,_OER)
#elif defined ( CONFIG_UNC90_USE_A4_LED )
  #define	PIO_MASK	AT91C_PIO_PB1
  #define	PIO_CODR	PIO_REG(B,_CODR)
  #define	PIO_SODR	PIO_REG(B,_SODR)	
  #define	PIO_ODSR	PIO_REG(B,_ODSR)
  #define	PIO_PER		PIO_REG(B,_PER)
  #define	PIO_OER		PIO_REG(B,_OER)
#else
 #error Led support is configured for UNC90 and no Led was selected
#endif

#else
#error CPU specific Status LED header file missing.
#endif

extern void status_led_set (int led, int state);

/* led_id_t is unsigned int mask */
typedef unsigned int led_id_t;

#ifdef CONFIG_SMDK2410_LED

static inline void __led_init (led_id_t mask, int state)
{
//	S3C24X0_GetBase_GPIO()->GPFCON = (0x0001<<mask);
//	S3C24X0_GetBase_GPIO()->GPFDAT = 0x0FF;	//switch off all LEDs

#if (STATUS_LED_ACTIVE == 0)
	if (state == STATUS_LED_ON)
		S3C24X0_GetBase_GPIO()->GPFDAT &= ~(mask & 0xFF);
	else
		S3C24X0_GetBase_GPIO()->GPFDAT |= (mask & 0xFF);
#else
	if (state == STATUS_LED_ON)
		S3C24X0_GetBase_GPIO()->GPFDAT |= (mask & 0xFF);
	else
		S3C24X0_GetBase_GPIO()->GPFDAT &= ~(mask & 0xFF);
#endif
}

static inline void __led_toggle (led_id_t mask)
{
	S3C24X0_GetBase_GPIO()->GPFDAT ^= (mask & 0xFF);
}

static inline void __led_set (led_id_t mask, int state)
{
#if (STATUS_LED_ACTIVE == 0)
	if (state == STATUS_LED_ON)
		S3C24X0_GetBase_GPIO()->GPFDAT &= ~(mask & 0xFF);
	else
		S3C24X0_GetBase_GPIO()->GPFDAT |= (mask & 0xFF);
#else
	if (state == STATUS_LED_ON)
		S3C24X0_GetBase_GPIO()->GPFDAT |= (mask & 0xFF);
	else
		S3C24X0_GetBase_GPIO()->GPFDAT &= ~(mask & 0xFF);
#endif
}

#elif CONFIG_CC9C_LED

static inline void __led_init (led_id_t mask, int state)
{
/* mask is GPIO-number */
	set_gpio_cfg_reg_val(mask,NS9750_GPIO_CFG_FUNC_GPIO | NS9750_GPIO_CFG_OUTPUT);
#if (STATUS_LED_ACTIVE == 0)
	if (state == STATUS_LED_ON)
		set_gpio_ctrl_reg_val(mask,0);
	else
		set_gpio_ctrl_reg_val(mask,1);
#else
	if (state == STATUS_LED_ON)
		set_gpio_ctrl_reg_val(mask,1);
	else
		set_gpio_ctrl_reg_val(mask,0);
#endif
}

static inline void __led_toggle (led_id_t mask)
{
/* mask is GPIO-number */
	set_gpio_ctrl_reg_val(mask,!(get_gpio_stat(mask)));
}

static inline void __led_set (led_id_t mask, int state)
{
/* mask is GPIO-number */
#if (STATUS_LED_ACTIVE == 0)
	if (state == STATUS_LED_ON)
		set_gpio_ctrl_reg_val(mask,0);
	else
		set_gpio_ctrl_reg_val(mask,1);
#else
	if (state == STATUS_LED_ON)
		set_gpio_ctrl_reg_val(mask,1);
	else
		set_gpio_ctrl_reg_val(mask,0);
#endif
}

#elif CONFIG_UNC90

static inline void __led_init( led_id_t mask, int state )
{
	/* Enable PIO to access the LEDs */
	*PIO_PER = PIO_MASK;
	*PIO_OER = PIO_MASK;
	
	if( state == STATUS_LED_ON )
		*PIO_CODR = PIO_MASK;
	else
		*PIO_SODR = PIO_MASK;
}

static inline void __led_toggle( led_id_t mask )
{
	unsigned long curr = *PIO_ODSR;
	
	// @TODO
	// mask is used for...
	
	if( curr & PIO_MASK )
		*PIO_CODR = PIO_MASK;
	else
		*PIO_SODR = PIO_MASK;
}

static inline void __led_set( led_id_t mask, int state )
{
	// @TODO
	// mask is used for...
	
	if( state == STATUS_LED_ON )
		*PIO_CODR = PIO_MASK;
	else
		*PIO_SODR = PIO_MASK;
}

#endif	// CONFIG_UNC90

#endif

#endif	/* __ASM_STATUS_LED_H__ */
