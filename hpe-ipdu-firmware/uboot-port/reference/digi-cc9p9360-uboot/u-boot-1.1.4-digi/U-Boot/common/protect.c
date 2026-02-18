#include <common.h>
#include <config.h>

void u_boot_protect( int addr, int size )
{
#if 0
	if( addr < _armboot_start - CFG_MALLOC_LEN  )
		printf("\nhello_0 addr: 0x%X  size: 0x%X  STACK: 0x%X", addr, size, CONFIG_STACKSIZE);
	if(( (_armboot_start - CONFIG_STACKSIZE) <= addr) && (addr <= _bss_end))
		printf("\nhello_1");
	if((addr < _armboot_start - CFG_MALLOC_LEN) && (addr + size >= _armboot_start - CFG_MALLOC_LEN))
		printf("\nhello_2");
#endif
	if( (( (_armboot_start - CONFIG_STACKSIZE) <= addr) && (addr <= _bss_end)) 
		|| ((addr < _armboot_start - (CFG_MALLOC_LEN + size )) && (addr + size >= _armboot_start - (CFG_MALLOC_LEN + size )))
		|| ((addr < _armboot_start - CFG_MALLOC_LEN ) && (addr + size >= _armboot_start - CFG_MALLOC_LEN)))
	{
		printf("\nCannot overwrite myself... Please use another address!\n");
		/* disable autoboot and go back to main loop */
		run_command("setenv bootcmd", 0);
		run_command("setenv bootdelay", 0);
		main_loop();
	}
}
