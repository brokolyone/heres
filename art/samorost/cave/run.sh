#!/bin/sh
# usage: sh run.sh tag
cd /home/user/heres/art/samorost
python3 cave/build.py && node cave/zoom.js cave/v_$1 samorost.svg layers/cave.svg cave/light.svg cave/grain_preview.svg && python3 -c "
from PIL import Image; im=Image.open('cave/v_$1_1x.png'); im.resize((im.width*3,im.height*3),Image.LANCZOS).save('cave/v_$1_1x.png')"
