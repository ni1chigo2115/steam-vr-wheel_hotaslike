# -*- coding: utf-8 -*-
"""
AC風テスト用: HUD の緑の画像 (操作インジゲータなど) をミント色に塗り替えた別名コピーを作る。
元の画像は変更しない。Python 3.5 + Pillow で動く。

使い方 (steam_vr_wheel フォルダの1つ上で):
    python make_mint_png.py
    python make_mint_png.py 150 255 190     (色を変えたいとき r g b)
作られるファイル (media/hotas_sacc/ の中):
    input_hud_mint.png / yawline_mint.png / cross_mint.png / cross_pov_aa_mint.png
塗り方: 元の緑の明るさ (G の値) に比例して新しい色を掛ける。アルファ (形) はそのまま。
"""
import os
import sys
from PIL import Image

FILES = ['input_hud.png', 'yawline.png', 'cross.png', 'cross_pov_aa.png']
COLOR = (130, 255, 180)      # 既定のミント。パッチの HUD_COLOR_GREEN と同じ値


def find_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    for d in [os.path.join(here, 'steam_vr_wheel', 'media', 'hotas_sacc'),
              os.path.join(here, 'media', 'hotas_sacc'),
              here]:
        if os.path.isfile(os.path.join(d, 'input_hud.png')):
            return d
    return None


def recolor(img, rgb):
    img = img.convert('RGBA')
    r, g, b, a = img.split()
    out = [g.point(lambda v, c=c: int(v * c / 255.0 + 0.5)) for c in rgb]
    return Image.merge('RGBA', out + [a])


def main():
    rgb = COLOR
    if len(sys.argv) == 4:
        rgb = tuple(int(v) for v in sys.argv[1:4])
    d = find_dir()
    if d is None:
        print('media/hotas_sacc が見つかりません。steam_vr_wheel フォルダの1つ上に置いて実行してください。')
        return
    for name in FILES:
        src = os.path.join(d, name)
        if not os.path.isfile(src):
            print('ありません (とばします): ' + src)
            continue
        dst = os.path.join(d, name[:-4] + '_mint.png')
        recolor(Image.open(src), rgb).save(dst)
        print('作りました: ' + dst)


if __name__ == '__main__':
    main()
