// SPDX-License-Identifier: GPL-2.0+
/*
 * Aspeed AST2050 (G3) Vectored Interrupt Controller.
 *
 * The AST2050 VIC is the *compact G3* variant: a single 32-bit bank with 4-byte
 * register spacing (0x00-0x38), NOT the AST2400/AST2500 two-bank layout with
 * 8-byte spacing that drivers/irqchip/irq-aspeed-vic.c handles. Crucially, the
 * G3's trigger-configuration registers (VIC24 sensitivity / VIC28 both-edge /
 * VIC2C event) reset to 0 and must be *programmed by firmware* (datasheet §16),
 * whereas the AST2400 hardwires them. The mainline driver only reads them, so it
 * cannot drive the G3 — hence this dedicated driver.
 *
 * Trigger config for the AST2050 IRQ map (reconstructed from the datasheet IRQ
 * table + verified on real silicon via culvert): SENSE=0x903897fe,
 * DUAL_EDGE=0x07c00000, EVENT=0x983f97fe. See
 * asus-kgpe-d16-firmware/qemu-model/peripherals/vic/DATASHEET-VIC.md.
 *
 * Register model + edge latching are emulated faithfully by QEMU's
 * aspeed.vic-ast2050 (hw/intc/aspeed_vic.c).
 *
 * Based on drivers/irqchip/irq-aspeed-vic.c (Benjamin Herrenschmidt, IBM Corp).
 */
#include <linux/export.h>
#include <linux/init.h>
#include <linux/io.h>
#include <linux/irq.h>
#include <linux/irqchip.h>
#include <linux/irqdomain.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/slab.h>
#include <asm/exception.h>
#include <asm/irq.h>

/* Compact G3 register file: single 32-bit bank, 4-byte spacing. */
#define G3VIC_IRQ_STATUS	0x00
#define G3VIC_FIQ_STATUS	0x04
#define G3VIC_RAW_STATUS	0x08
#define G3VIC_INT_SELECT	0x0c
#define G3VIC_INT_ENABLE	0x10
#define G3VIC_INT_ENABLE_CLR	0x14
#define G3VIC_SOFT_INT		0x18
#define G3VIC_SOFT_INT_CLR	0x1c
#define G3VIC_INT_SENSE		0x24
#define G3VIC_INT_DUAL_EDGE	0x28
#define G3VIC_INT_EVENT		0x2c
#define G3VIC_EDGE_CLR		0x38

#define G3VIC_NUM_IRQS		32

/*
 * AST2050 trigger configuration (firmware programs these on the G3). 1 in SENSE
 * = level-sensitive, 0 = edge; DUAL_EDGE 1 = both edges; EVENT 1 = high/rising.
 */
#define G3VIC_SENSE_INIT	0x903897feU
#define G3VIC_DUAL_EDGE_INIT	0x07c00000U
#define G3VIC_EVENT_INIT	0x983f97feU

struct aspeed_g3_vic {
	void __iomem		*base;
	u32			edge_sources;
	struct irq_domain	*dom;
};

static struct aspeed_g3_vic *g3_avic;

static void g3vic_init_hw(struct aspeed_g3_vic *vic)
{
	/* Disable all interrupts, route everything to IRQ (not FIQ). */
	writel(0xffffffff, vic->base + G3VIC_INT_ENABLE_CLR);
	writel(0xffffffff, vic->base + G3VIC_SOFT_INT_CLR);
	writel(0, vic->base + G3VIC_INT_SELECT);

	/*
	 * Program the trigger configuration. Unlike the AST2400 (hardwired), the
	 * G3 resets these to 0, so firmware must set them; do it here.
	 */
	writel(G3VIC_SENSE_INIT, vic->base + G3VIC_INT_SENSE);
	writel(G3VIC_DUAL_EDGE_INIT, vic->base + G3VIC_INT_DUAL_EDGE);
	writel(G3VIC_EVENT_INIT, vic->base + G3VIC_INT_EVENT);

	/* Edge sources are those NOT marked level-sensitive in SENSE. */
	vic->edge_sources = ~readl(vic->base + G3VIC_INT_SENSE);

	/* Clear any latched edge detections. */
	writel(0xffffffff, vic->base + G3VIC_EDGE_CLR);
}

static void g3vic_ack_irq(struct irq_data *d)
{
	struct aspeed_g3_vic *vic = irq_data_get_irq_chip_data(d);
	u32 sbit = 1u << (d->hwirq & 0x1f);

	if (vic->edge_sources & sbit)
		writel(sbit, vic->base + G3VIC_EDGE_CLR);
}

static void g3vic_mask_irq(struct irq_data *d)
{
	struct aspeed_g3_vic *vic = irq_data_get_irq_chip_data(d);

	writel(1u << (d->hwirq & 0x1f), vic->base + G3VIC_INT_ENABLE_CLR);
}

static void g3vic_unmask_irq(struct irq_data *d)
{
	struct aspeed_g3_vic *vic = irq_data_get_irq_chip_data(d);

	writel(1u << (d->hwirq & 0x1f), vic->base + G3VIC_INT_ENABLE);
}

static struct irq_chip g3vic_chip = {
	.name		= "G3-VIC",
	.irq_ack	= g3vic_ack_irq,
	.irq_mask	= g3vic_mask_irq,
	.irq_unmask	= g3vic_unmask_irq,
};

static void __exception_irq_entry g3vic_handle_irq(struct pt_regs *regs)
{
	struct aspeed_g3_vic *vic = g3_avic;
	u32 stat;

	for (;;) {
		stat = readl_relaxed(vic->base + G3VIC_IRQ_STATUS);
		if (!stat)
			break;
		generic_handle_domain_irq(vic->dom, ffs(stat) - 1);
	}
}

static int g3vic_map(struct irq_domain *d, unsigned int irq,
		     irq_hw_number_t hwirq)
{
	struct aspeed_g3_vic *vic = d->host_data;
	u32 sbit = 1u << (hwirq & 0x1f);

	if (hwirq >= G3VIC_NUM_IRQS)
		return -EPERM;

	if (vic->edge_sources & sbit)
		irq_set_chip_and_handler(irq, &g3vic_chip, handle_edge_irq);
	else
		irq_set_chip_and_handler(irq, &g3vic_chip, handle_level_irq);
	irq_set_chip_data(irq, vic);
	irq_set_probe(irq);
	return 0;
}

static const struct irq_domain_ops g3vic_dom_ops = {
	.map	= g3vic_map,
	.xlate	= irq_domain_xlate_onetwocell,
};

static int __init g3vic_of_init(struct device_node *node,
				struct device_node *parent)
{
	void __iomem *regs;
	struct aspeed_g3_vic *vic;

	if (WARN(parent, "non-root Aspeed G3 VIC not supported"))
		return -EINVAL;
	if (WARN(g3_avic, "duplicate Aspeed G3 VIC not supported"))
		return -EINVAL;

	regs = of_iomap(node, 0);
	if (WARN_ON(!regs))
		return -EIO;

	vic = kzalloc(sizeof(*vic), GFP_KERNEL);
	if (WARN_ON(!vic)) {
		iounmap(regs);
		return -ENOMEM;
	}
	vic->base = regs;

	g3vic_init_hw(vic);

	g3_avic = vic;
	set_handle_irq(g3vic_handle_irq);

	vic->dom = irq_domain_add_simple(node, G3VIC_NUM_IRQS, 0,
					 &g3vic_dom_ops, vic);
	return 0;
}

IRQCHIP_DECLARE(ast2050_vic, "aspeed,ast2050-vic", g3vic_of_init);
