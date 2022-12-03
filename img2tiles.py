#!/usr/bin/env python3

from ntpath import join
import sys
import argparse

SMS_MAX_COLORS = 64
SMS_PALETTE_SIZE = 32
SMS_COLS_PER_CH = 4
SMS_TILE_SIZE = 8

parser = argparse.ArgumentParser(description='Convert bitmap file to tile data.')
parser.add_argument('file', nargs='?', type=argparse.FileType('rb'), default=sys.stdin, help='the bitmap (.bmp or .tga) file to process')
parser.add_argument('-o', '--output', choices=['asm', 'c'], default='asm', help='the output type, z80 assembler or C')
parser.add_argument('-c', '--colors', action=argparse.BooleanOptionalAction, default=True, help='output the color table (palette)')

args = parser.parse_args()

def read_bmp(file):

    # Read BMP file header
    signature = file.read(2)
    if signature != b'BM':
        raise Exception(f"Unexpected BMP signature (was {signature})")
    file.read(8) # 4 bytes file size (can be ignored); 2x 2 bytes reserved
    image_data_offset = int.from_bytes(file.read(4), byteorder='little')
    dib_size = int.from_bytes(file.read(4), byteorder='little')
    if dib_size != 40:
        raise Exception(f"Unexpected DIB size (was {dib_size})")
    width = int.from_bytes(file.read(4), byteorder='little')
    height = int.from_bytes(file.read(4), byteorder='little')
    file.read(2) # color planes (always 1)
    bpp = int.from_bytes(file.read(2), byteorder='little')
    compression = int.from_bytes(file.read(4), byteorder='little')
    if compression != 0:
        raise Exception(f"Unsupported compression type (was {compression})")
    file.read(12) # 4 bytes raw bitmap size; 4 bytes h resolution; 4 bytes v resolution (can all be ignored)
    palette_size = int.from_bytes(file.read(4), byteorder='little')
    if palette_size == 0:
        palette_size = 2 ** bpp
    file.read(4) # important color count (can be ignored)

    palette = []
    # Read palette
    for _ in range(palette_size):
        b = int.from_bytes(file.read(1), byteorder='little') & (SMS_COLS_PER_CH - 1)
        g = int.from_bytes(file.read(1), byteorder='little') & (SMS_COLS_PER_CH - 1)
        r = int.from_bytes(file.read(1), byteorder='little') & (SMS_COLS_PER_CH - 1)
        file.read(1) # alpha
        palette.append(r + SMS_COLS_PER_CH * (g + SMS_COLS_PER_CH * b))

    row_size = 1 + (width - 1) // SMS_TILE_SIZE
    tiles = [None] * row_size * (1 + (height - 1) // SMS_TILE_SIZE)
    pixels_per_byte = 8 // bpp
    packed_pixels = 0
    for y in reversed(range(height)):
        for x in range(width):
            tile_x = x // SMS_TILE_SIZE
            tile_y = y // SMS_TILE_SIZE
            tile = tiles[tile_y * row_size + tile_x]
            if tile == None:
                tile = [[0] * SMS_TILE_SIZE for i in range(SMS_TILE_SIZE)]
                tiles[tile_y * row_size + tile_x] = tile
            if packed_pixels == 0:
                idx = int.from_bytes(file.read(max(1, bpp // 8)), byteorder='little')
                packed_pixels = pixels_per_byte

            packed_pixels = packed_pixels - 1
            tile[y % SMS_TILE_SIZE][x % SMS_TILE_SIZE] = (idx >> (packed_pixels * bpp)) & ((2 ** bpp) - 1)
        # Rows are padded to multiple of four bytes
        padding = 4 * (1 + ((bpp * (width - 1)) // 32)) - (1 + (bpp * (width - 1)) // 8)
        for _ in range(padding):
            file.read(1)

    return (tiles, palette)

def print_asm(tiles, palette):
    print("; palette")
    for i in range(SMS_PALETTE_SIZE):
        if i < len(palette):
            print('.db ${:02x}; color {:02x}'.format(palette[i], i))
        else:
            print('.db $00; color {:02x} (undefined)'.format(i))
        
    print()
    for i, tile in enumerate(tiles):
        print(f"; tile {i}")
        for row in tile:
            row_bytes = []
            for p in range(4):
                byte = 0
                for px in row:
                    byte = (byte << 1) + ((px >> p) & 1)
                row_bytes.append('${:02x}'.format(byte))
            print(f".db {','.join(row_bytes)}")

def print_c(tiles, palette):
    bg_colors = []
    sprite_colors = []
    for i in range(SMS_PALETTE_SIZE):
        if i < len(palette):
            color = palette[i]
        else:
            color = 0
        if i < 16:
            bg_colors.append('0x{:02x}'.format(color))
        else:
            sprite_colors.append('0x{:02x}'.format(color))
    print("const unsigned char bg_colors[] = {")
    print(f"  {', '.join(bg_colors)}")
    print("};")
    print("const unsigned char sprite_colors[] = {")
    print(f"  {', '.join(sprite_colors)}")
    print("};")
        
    print()
    print("const unsigned char all_tiles[][32] = {")
    all_bytes = []
    for i, tile in enumerate(tiles):
        tile_bytes = []
        for row in tile:
            for p in range(4):
                byte = 0
                for px in row:
                    byte = (byte << 1) + ((px >> p) & 1)
                tile_bytes.append('0x{:02x}'.format(byte))
        all_bytes.append(f"  {{ {', '.join(tile_bytes)} }}")
    print(',\n'.join(all_bytes))
    print("};")

(tiles, palette) = read_bmp(args.file)
if args.output == "asm":
    print_asm(tiles, palette)
else:
    print_c(tiles, palette)
