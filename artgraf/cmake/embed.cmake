# Turns a binary file into a C++ source with a byte array.
#   cmake -DIN=logo.png -DOUT=embedded_logo.cpp -DNAME=kLogoPng -P embed.cmake
file(READ "${IN}" hex HEX)
string(LENGTH "${hex}" len)
math(EXPR size "${len} / 2")
string(REGEX REPLACE "([0-9a-f][0-9a-f])" "0x\\1," bytes "${hex}")
file(WRITE "${OUT}" "#include <cstddef>\nextern const unsigned char ${NAME}[] = {${bytes}};\nextern const std::size_t ${NAME}Size = ${size};\n")
