# steam-vr-wheel (hotaslike fork)

**Personal experimental fork. Please do not share, promote, or redistribute it.**

- Only aims at extending the joystick mode. Wheel and other modes are not maintained.
- Experimental. Things break and change without notice.
- Much of the code was written with LLM (AI) assistance. No guarantees.
- No support. Issues and questions will not be answered. Use at your own risk.

Fork of [steam-vr-wheel](https://github.com/mdovgialo/steam-vr-wheel) 2.5.4a.
VR controllers as a flight stick and throttle (vJoy output), with a HUD as a SteamVR overlay.

## Run

Needs Windows, SteamVR, vJoy, Python 3.5.3 (64bit). Libraries: [DEPENDENCIES.md](DEPENDENCIES.md).

```
pip install .
vrjoystick
```

Ctrl+C in the console to stop.

## Controls

- Right grip: grab the stick
- Left grip: grab the throttle
- Touch left touchpad / app menu: POV (d-pad)
- Console keys: `C` wrist calibration, `H` HUD recenter, `F` HUD mode, `L` log view (others: top of `steam_vr_wheel/_joystick.py`)

## License

MIT, same as the original steam-vr-wheel (mdovgialo). See [LICENSE](LICENSE).
Fonts and other notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

<details>
<summary>ja</summary>

**個人用の実験フォークです。配布・紹介・転載はしないでください。**

- ジョイスティック (操縦桿・スロットル) の拡張だけが目的です。ハンドル (wheel) などの機能は手入れしていません。
- 実験段階です。壊れます。仕様も予告なく変わります。
- コードの多くは LLM (AI) との作業で書いたものです。中身の保証はありません。
- 質問・要望・Issue には答えません。使うなら自己責任でどうぞ。

## なにか

[steam-vr-wheel](https://github.com/mdovgialo/steam-vr-wheel) 2.5.4a の改造版。
VR コントローラーで操縦桿とスロットルを動かし、vJoy に出します。SACC 風の HUD を SteamVR オーバーレイで出します。

## 動かす

要るもの: Windows / SteamVR / vJoy / Python 3.5.3 (64bit)。ライブラリは [DEPENDENCIES.md](DEPENDENCIES.md)。

```
pip install .
vrjoystick
```

止めるときはコンソールで Ctrl+C。

## さわりかた

- 右グリップでつかむ → 操縦桿
- 左グリップでつかむ → スロットル
- 左のタッチパッド / アプリメニューに触れる → 十字キー (POV)
- コンソールのキー: `C` 手首の計測、`H` HUD の位置合わせ、`F` HUD の見せ方切り替え、`L` ログ表示切り替え (ほかは `steam_vr_wheel/_joystick.py` の先頭)

## ライセンス

元の steam-vr-wheel (mdovgialo) と同じ MIT。[LICENSE](LICENSE) を見てください。
フォントなどの表記は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

</details>
