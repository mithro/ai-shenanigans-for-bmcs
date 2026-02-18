/*
 *  include/configs/digi_common.h
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
 *  !Descr:      Defines all definitions that are common to all DIGI platforms
*/

#ifndef __DIGI_COMMON_H
#define __DIGI_COMMON_H

#define CONFIG_COMMANDS_DIGI (  \
         ( CONFIG_CMD_DFL  & \
           ~CFG_CMD_FLASH ) | \
         CFG_CMD_BSP       |  /* DIGI commands like dboot and update */ \
         CFG_CMD_CACHE     |   /* icache, dcache */ \
         CFG_CMD_DATE      | \
         CFG_CMD_DHCP      | \
         CFG_CMD_ELF       | \
         CFG_CMD_FAT       | \
         CFG_CMD_I2C       | \
         CFG_CMD_IMI       | \
         CFG_CMD_JFFS2     | \
         CFG_CMD_NET       | \
         CFG_CMD_PING      | \
         CFG_CMD_REGINFO   | \
         CFG_CMD_SNTP      |   /* simple network time protocol */ \
         CFG_CMD_USB       | \
         0 )

#endif /* __DIGI_COMMON_H */
