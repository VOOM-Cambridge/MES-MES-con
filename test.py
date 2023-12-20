from freppleAPImodule import freppleConnect

frepple = freppleConnect("admin", "admin", "http://129.169.48.176:9000")

outNotConfirmend = frepple.findAllPurchaseOrdersOrd("RL100100", "proposed")

print(outNotConfirmend)