# 動作に必要な Python ライブラリ

このフォーク (steam-vr-wheel 2.5.4a 改造版 + SACC 風 HUD) を動かすのに要るライブラリの一覧です。
ライセンスの表記は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) にあります。

前提の環境: **Python 3.5.3 64bit (ポータブル版)**、Windows、SteamVR、vJoy。

## 1. `Lib.zip` に入っているもの

`Lib.zip` は Python 本体フォルダの `Lib\site-packages\` に展開する前提でまとめてあります。

| フォルダ (site-packages 直下) | パッケージ / 版 | 要るか | 何に使うか |
|---|---|---|---|
| `glfw`, `glfw-2.10.2.dist-info` | glfw (pyGLFW) 2.10.2 | **必須 (HUD)** | HUD 描画用の見えない OpenGL ウィンドウを作る。`glfw3.dll` 同梱 |
| `OpenGL`, `pyopengl-3.1.10.dist-info` | PyOpenGL 3.1.10 | **必須 (HUD)** | HUD のテクスチャ描画 (FBO、テクスチャ転送、ミップマップ) |
| `PIL`, `Pillow-7.2.0.dist-info` | Pillow 7.2.0 | **必須** | HUD の文字・画像の作成 (`Image`, `ImageDraw`, `ImageFont` ほか) |
| `pip`, `pip-20.3.4.dist-info` | pip 20.3.4 | 実行には不要 | インストール用の道具。Python 3.5 で使える最後の版 |
| `setuptools`, `setuptools-50.3.2.dist-info`, `pkg_resources`, `_distutils_hack`, `distutils-precedence.pth`, `easy_install.py` | setuptools 50.3.2 | 実行には不要 | `pip install .` (setup.py) のときだけ使う。Python 3.5 で使える最後の版 |
| `wheel`, `wheel-0.37.1.dist-info` | wheel 0.37.1 | 実行には不要 | パッケージ作成用。Python 3.5 で使える最後の版 |
| `__pycache__` | (キャッシュ) | 不要 | 自動で作り直される |

### glfw と PyOpenGL について

HUD は SteamVR のオーバーレイに OpenGL のテクスチャを渡して表示しています。
そのため `steam_vr_wheel/_joystick.py` の `HudGLContext` が `glfw` と `OpenGL.GL` を読み込みます。
元の steam-vr-wheel には含まれていないので、別途入れる必要があります。

- 読み込むのは HUD を作る時だけです (`HudGLContext.__init__` の中で import)。
- 入っていない場合はコンソールに `[HUD Error] HUD plate init failed (ImportError: ...)` と出て HUD は表示されません。
  例外は捕まえているので、ジョイスティック (vJoy 出力) はそのまま動きます。
- PyOpenGL 内部の `pkg_resources` / `setuptools` の利用はありません (同梱の `OpenGL/plugins.py` で確認)。

### 不要そうなもの

pip / setuptools / wheel (と付属の `pkg_resources`, `_distutils_hack`) はプログラムからは使っていません。
ただし `pip install .` で steam_vr_wheel 自体をインストールし直すときには setuptools が要ります。
pip で何か追加する予定があるなら、残しておくのが無難です。

## 2. `Lib.zip` に入っていないが必須のもの

| パッケージ | 版 | 何に使うか |
|---|---|---|
| **pyopenvr** (`openvr`) | **1.0.0701** | SteamVR との通信全般。新しい版は API が違うので、この版に固定 |
| numpy | (元の環境のもの) | `wheel.py` が `_wheel.py` を起動時に読み込み、そこで import している |
| wxPython | (元の環境のもの、setup.py では 4.0.0a3) | `wheel.py` が `configurator.py` を起動時に読み込み、そこで import している |
| vJoy (ドライバ) | — | ゲームへの出力。`steam_vr_wheel/pyvjoy/vJoyInterface.dll` を同梱済み。ドライバ本体は別途インストール |

numpy と wxPython はジョイスティックモードでは中身を使っていませんが、
`wheel.py` の先頭で読み込まれるので、無いと起動できません。
元の steam-vr-wheel のポータブル環境にはこの3つが入っているはずです。

## 3. 入れ方

1. Python 3.5.3 64bit ポータブル版のフォルダを開く (`python.exe` がある所)。
2. `Lib.zip` を展開し、中の `Lib\site-packages\` の中身を、Python 側の `Lib\site-packages\` にコピーする。
   - 既にある `openvr`, `numpy`, `wx` などは消さないこと (フォルダごと置き換えない)。
3. 確認: そのフォルダでコマンドプロンプトを開き、次を実行してエラーが出なければ OK。

   ```
   python -c "import glfw, OpenGL.GL, PIL, openvr, numpy, wx; print(glfw.__version__, OpenGL.__version__, PIL.__version__)"
   ```

   `2.10.2 3.1.10 7.2.0` と表示されれば、zip の中身は正しく入っています。
