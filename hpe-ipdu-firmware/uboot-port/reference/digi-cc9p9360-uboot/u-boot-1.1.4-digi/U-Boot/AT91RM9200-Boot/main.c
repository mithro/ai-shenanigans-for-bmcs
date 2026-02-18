extern void AT91F_UNC90_Printk(char *);
extern int copy_image(void *src, void *dst, unsigned int len);


extern char _stext,_etext,_sdata,_edata;

#define BOOT_VERSION	"UNC90 boot 1.0-FS.1"

#define SRC 0x10010000
#define DST 0x20f00000
#define LEN 0x00030000


void boot() {
	int i;
	char* ptr=(char*)DST;
	  
	for(i=0;i<LEN;i++) ptr[i]=0;
	  
	AT91F_UNC90_Printk ("\n\n\r"BOOT_VERSION" (" __DATE__ " - " __TIME__ ")\n\r");

#ifdef UNCOMPRESS_UBOOT
	AT91F_UNC90_Printk("\n\rUncompressing image...\n\n\r");
	decompress_image(SRC,DST,LEN);
#else
	AT91F_UNC90_Printk("\n\rCopying image...\n\n\r");
	copy_image( (void *)SRC, (void *)DST, LEN );  
#endif

	asm("mov pc,%0" : : "r" (DST));
};

void recover(char* s) {
	for(;;);
};
