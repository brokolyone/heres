import sys, os, math; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hero_common import *
import assemble as asm
lod = int(sys.argv[1]) if len(sys.argv) > 1 else 0
reset(); p = asm.assemble(lod, library=(lod == 0))
p["leg_L"].rotation_euler.x = math.radians(35); p["leg_R"].rotation_euler.x = math.radians(-35)
preview(f"_swing{lod}", views=("side", ((V((1.2, 1.4, 0.35)), V((0, 0, 0.3))))), res=480)
