# -*- coding: utf-8 -*-
"""
steam_vr_wheel/_joystick.py ― SteamVR Virtual Cockpit: VR 操縦桿 + スロットル (vJoy 出力) と SACC 風 HUD

■ この説明は、後でこのファイルを触る人 / 他の LLM・チャット向け
  動作環境 (変えないこと):
    - Windows, ポータブル Python 3.5.3 64bit  → f文字列・型注釈・:=・数値の _ 区切り・*args の後ろのカンマは使えない。
      dict は順序が保証されないので、順序が大事な設定はリストにする。
    - pyopenvr 1.0.0701 (同梱の古い版)  → 新しい版と関数の引数が違うものがある (try/except TypeError で両対応している)。
        getDeviceToAbsoluteTrackingPose(universe, predict, count) / getComponentState(name, comp) など。
    - Pillow, glfw, PyOpenGL (HUD 用)。GPU は RTX 3060、ヘッドセットは Quest 3。
    - 呼び出し元: steam_vr_wheel/wheel.py が Joystick() を引数なしで作り、毎フレーム update(left_ctr, right_ctr)。
      self.device (vJoy), self.config は親クラス VirtualPad (_virtualpad.py) が用意する。継承順は変えないこと。
  設定:
    - ユーザーが変える変数には "# [CONFIG]" を付けてある (後で設定ファイルにまとめる予定)。新しい設定にも必ず付ける。
  コンソールのキー (DEBUG_KEYMAP で変えられる。中身は Joystick.debug_command('名前') なので、キー以外からも呼べる):
    - C : 左手首のピボット計測 (スロットルが手首の回転で動かないようにする) → throttle_pivot.json に保存
    - H : 今の頭の位置を HUD 奥行き表示の「基準の目の位置」にする (このセッションだけ。値が表示される)
    - F : HUD の見せ方を 'fakefar' (通常) → 'far' (最高の見え方) → 'plate' (互換) の順に切り替える (このセッションだけ)
          プログラムからは hud.set_mode('fakefar' / 'far' / 'plate')、hud.get_mode()
    - S : HUD の統計 (描き直しが間に合っているか) を 5 秒ごとに表示 / やめる
    - D : 頭の姿勢の届き方を 3 秒測る (届く回数 / ドライバーの速度 / 先読みが効いているか)
    - T : 'fakefar' のずらしの予測を「次に合成される画面が光る時刻」/「常に一定時間先」で切り替え (HUD_LATE_SHIFT_VSYNC_TARGET)
    - V : 'fakefar' のずらしの切り替えを、絵のコピー完了から 0/1/2/3 vsync 後に (HUD_LATE_SHIFT_SWITCH_VSYNC)
    - [ / ] : 頭の位置の予測に足す時間を -2ms / +2ms (HUD_DEPTH_PREDICT_EXTRA_SEC)。\\ で 0 に戻す
    - P / O : (調査用) スティックの数値の段を出す / 隠す、[DPAD] の1行ログを出す / 止める
    - G : (検証用) 位置の計算を別スレッドで: 切 → 姿勢だけ → 全部 (写し方・拡大縮小・ずらしも) (HUD_POSE_THREAD)
    - K / X / J : (HUD 揺れ調査用 JIT1) ずらしの入/切、絵の描き直しを絞る、調査用 CSV の記録 (下の版の説明を参照)
    - L : HUD のデバッグログを 普通 → 大きく → 隠す (コマンド 'hud_log_cycle')。ほかに 'hud_log_toggle' / 'hud_log_clear' / 'version' (キーなし)
  システム名とバージョン: APP_NAME ('SteamVR Virtual Cockpit') / APP_VERSION / APP_BASE_VERSION。
    起動時にコンソールへ表示。HUD は起動時に中央へ大きく出して消え (HUD_SPLASH_*、コマンド 'version' で出し直す)、
    通知の段 (Bマーク) の数段上 = HUD の右上の端に 'V0.1.5' の形で、右揃えで常に出す (HUD_VERSION_*)。変更を配るたびに APP_VERSION を上げること。
  0.1.5-DPAD1 (Q29-3 調査用、マージしない): 通知の段の下に、左右のサムスティックの生の値と VirtualDPad の判定の中身を
    出す段を足した (DPAD_DEBUG_*、P キー = コマンド 'dpad_debug' で出す / 隠す)。方向が変わるたびに [DPAD] の1行をログに出す。
  0.1.5-DPAD2: 数値の段をフォント確認 (アイコン) の段より上に移した。
  0.1.5-DPAD2-AC: 上に HUD 視認性の AC 風テスト (design/hud_readability/test_ac_look/hud_look_ac_test.patch:
    ミント色・不透明度 0.85・にじみ 5px/0.35・ぼかし 0.3、*_mint.png) を重ねたテスト版。
  0.1.5-DPAD3-AC: 左の操作インジケーターの十字キーアイコン (HUD_POV_FILE) だけ元の cross_pov_aa.png に戻した。
  0.1.5-DPAD3-AC-JIT1 (HUD 揺れ調査用): 実機でその場で切り替えて試すキーを足した。
    O = [DPAD] の1行ログを出す / 止める (DPAD_DEBUG_LOG)。P (数値の段) と合わせて切ると、スティックのログが消える。
    K = HUD_LATE_SHIFT (ずらし) を入 / 切。
    X = 'fakefar' の絵の描き直しを 通常 → 240 → 120 → 80 → 60 → 40 → 20 → 10 → 5 → 1回/秒 → 通常 に絞る (HUD_TEXTURE_FREEZE_HZ)。
        ずらしは今まで通り約 650回/秒。絞って高負荷でも揺れが消えれば「絵とずらしの切り替えのずれ」が原因と分かる。
        絞っている間は前後の動き (拡大縮小) と回転が遅れて見えるが、それは正常 (調べたいのは上下左右の小さな跳び)。
    J = 調査用 CSV (HUD_JITTER_CSV_*) の記録を始める / 止める。1行 = 1つの出来事 (submit / switch / shift)。
        列: t_ms (記録開始からの時刻), event, vsync (SteamVR の vsync 番号),
            pose_age_ms (submit: 頭の位置を読んでから渡し終わるまで), gpu_wait_ms (submit: GPU 待ち),
            since_submit_ms (switch: 渡してからずらしの基準が切り替わるまで),
            ref_x_mm / ref_y_mm (その絵を作った目), eye_x_mm / eye_y_mm (shift: 予測した目), dx_mm / dy_mm (shift: ずらし量),
            lead_ms (shift: 予測の先読み)。目の位置は seated の座標 (両目の真ん中)。
  0.1.6: 上の DPAD1～JIT1 (調査用の段とキー、AC風の見た目) をまとめて master に入れた。十字キーのアイコンもミント版
    (cross_pov_aa_mint.png) にして、ほかの HUD の色とそろえた。*_mint.png は make_mint_png.py (リポジトリの一番上。steam_vr_wheel の1つ上で実行) で作ったもの。
    デバッグのキーと CSV の仕様は docs/デバッグ機能.md にもまとめてある。
  0.1.7: 通知の段に現在時刻 (時:分:秒、PC の時計) の段を足した (HUD_CLOCK_*)。動画や CSV と見比べるため。
  0.1.8: X キーの段階に 240 / 120 / 80 / 60 / 40 / 20 回/秒を足した (HUD_TEXTURE_FREEZE_STEPS)。
  0.1.9 (検証用): G キー = 頭の位置の計算を別スレッドに分ける (HUD_POSE_THREAD)。入にすると 'hud_pose' スレッドが
    約 1ms ごとに「絵用の予測」と「ずらし用の予測」を計算して変数に入れ、描くときとずらすときはその最新の値を代入するだけになる。
    切 (既定) は今まで通り、描く直前とずらす直前にそれぞれ自分で読む。
  0.1.11 (検証用): G キーを 切 → 姿勢だけ → 全部 → 切 の3段に。'全部' (HUD_POSE_THREAD = 'full') では別スレッドが
    頭の姿勢の予測に加えて、目の位置・絵の写し方 (視差と拡大縮小) の計算と、ずらし量の計算・オーバーレイの移動まで行う。
    描く側 (OpenGL) は代入された写し方を読んで描くだけ、ずらしの基準の切り替え (コピー完了のフェンス) だけは描く側に残る
    (別スレッドは次の計算 (約 1ms 以内) で新しい基準を使う)。別スレッドの値が古ければ (HUD_POSE_THREAD_MAX_AGE_SEC) 描く側が自分で計算する。
  0.1.12 (デバッグ用): 時計の段を 0.1 秒まで出す (HUD_CLOCK_TENTHS、動画と CSV を合わせるため。普段使いでは False)。
    調査用 CSV に PC の時計の列 'clock' (時:分:秒.ミリ秒) を足した。
  0.1.13 (検証用): B キー = 基準の目で描く (HUD_FIXED_REF)。'fakefar' の絵を、今の頭の位置ではなく基準の目 E0
    (= SACC の設計どおりの見え方。HUD_DEPTH_EYE_OFFSET) から見た形で描き、頭の動きはすべてずらし (上下左右 + 前後) で直す。
    絵の中身 (計器・数字) はこれまでどおり更新するが、絵に焼き込む頭の位置が変わらないので、絵が届くたびの跳びが出ない (はず)。
    2026-10-17 の実機 (GPU 待ちが約 100ms の VRSNS) で、絵の描き直しのたびに HUD が跳ぶことがわかったため。
    U キー = 基準の十字線 (HUD_DEBUG_CROSSHAIR): 基準の目の真正面 (20m 先に見える HUD の中心) に十字を描く。
    HUD のログを短くする (HUD_LOG_SHORTEN: 括弧の中の説明を省く。コンソールには全文が残る)。折り返しは 6 行まで。
  デバッグログ: print した文字はコンソール (ログとして残す) と HUD の両方に出る (sys.stdout を _HudLogTee に差し替え)。
    HUD では操作インジゲータの上に左揃え、新しい行ほど下。行数は自動 (上端がバージョン表記を越えない)。
    普通 / 大きく の2つの層を同じ場所に取り、HUD_LOG.mode に合う方だけ出す。文字はにじみなし・不透明・濃い薄板 (読みやすさ優先)。
    HUD_LOG_* で設定。hud_log('文字') でも送れる。Hornet に無い文字 ('[' や日本語) は日本語フォントで描く。

■ 構成 (上から順)
  [CONFIG] HUD 設定 / スロットル・リミッター設定 / フォントとボタン記号 (HudFonts)
  HUD (1枚板方式のみ。旧「部品ごとに複数オーバーレイ」方式は削除済み):
    HudAssets       素材 (media/hotas_sacc/ → media/) の読込。透明な余白は切り詰める
    HudLayout       2D レイアウトだけ。部品の大きさと位置 [px] を決める (奥行き・OpenVR を知らない)
    HudDepth        奥行き (視差) の計算だけ。頭の位置から「板に絵をどう写すか」(拡大率, ずらし) を返す
    HudNoticeBoard  システム通知の段 (Bマークなど)。信号 → どの段を何色で出すか (描画を知らない)
    薄板 (HUD_PANEL_*): 線・文字の下はくり抜く (HUD_PANEL_KNOCKOUT, _hud_blit_ko)。線の色に薄板の灰色を混ぜないため。
    HudLog          デバッグログの行をためる (描画を知らない)。HUD_LOG 1つ。_HudLogTee が print をここにも送る。
                    HudPlateOverlay の 'log' 層 (_log_key / _render_log) が操作インジゲータの上に描く
    HudGLContext    OpenGL の環境 (見えない glfw ウィンドウ)。今後オーバーレイを増やしても共有する
    HudPlateOverlay 上を使って描く。素材テクスチャ (PIL で部品を合成、変わった所だけ転送)
                    → FBO で奥行きの写し方を付けて出力テクスチャへ → SteamVR オーバーレイ1枚に渡す。
                    見せ方 (HUD_DEPTH_MODE / set_mode): 'far' = 出力テクスチャを HUD_DEPTH_DISTANCE_M 奥の大きなオーバーレイに渡す。
                    記号の位置は SteamVR が合わせ、こちらは板(窓)からの見える範囲を scissor で切り抜くだけ。
                    'fakefar' (既定) = 同じオーバーレイを板の HUD_FAKEFAR_DIST_M 奥に置き、20m 先に見えるよう写し方を付ける
                    (SteamVR 2.17+ のストリーミングでは重なりが距離で決まり、遠いと他のオーバーレイに隠れるため)。
                    板の位置のオーバーレイには縦線だけ。'plate' は板の上で拡大・ずらしして描く (HudDepth.mapping)。
                    HUD_POSE_SOURCE='hybrid' (既定, fakefar/far): オーバーレイは SteamVR が最新の頭の位置で置き直すが、
                    ゲームの画面は描いたときの頭の位置のまま。なので見える方向はゲームの頭の位置、描く場所は最新の頭の位置から
                    計算し (_far_map の eye_dir)、vsync ごとに描く。ゲームの頭の位置は「画面に出る vsync」まで予約して切り替える。
                    HUD_GAME_SYNC: HUD はすぐ描くが、SteamVR に渡すのはゲームのフレームが画面に出る直前の vsync の後
                    (ゲームの FPS から見積もる)。すぐ渡すと前のゲームの画面と一緒に出ることがあり、揺れになるため。
                    頭の位置 (HUD_POSE_SOURCE='game'): ゲームが描画に使った姿勢 (GetLastPoseForTrackedDeviceIndex) を使い、
                    ゲームのフレームが変わるたびに描き直す。FPS が低くても景色と HUD がずれない。取れなければ予測 (predict)。
                    描くのは専用スレッド (HUD_THREADED)。vsync ごとに1回、その瞬間に見える頭の位置を予測して描く。
                    update_hud_state() は値を預けるだけ。GL の環境はそのスレッドだけが使う。
                    内部の絵は HUD_RENDER_SCALE 倍の細かさ。縮小はミップマップ (glGenerateMipmap) でなめらかにする。
                    出力の解像度は自動でヘッドセットの画素の細かさに合わせる (HUD_TEXTURE_SCALE = None)。
                    立体視 (HUD_STEREO) では左目用・右目用の絵を横に並べ、オーバーレイの
                    SideBySide_Parallel フラグで左右の目に別々に見せる (目の位置 = 頭の姿勢 + getEyeToHeadTransform)。
                    板 (オーバーレイ) の位置は動かさない (動かすと他のオーバーレイに隠れるため)。
                    例外 HUD_LATE_SHIFT ('display' で描き続ける fakefar): ゲームが GPU を使い切ると glFinish が 8～10ms 待たされ、
                    描く回数と頭の位置の新しさが vsync / ゲームに縛られる (上下左右の揺れ)。そこで GPU 待ちはフェンスで見張り、
                    その間も約 1ms ごとに「絵を作った目と最新の予測の目の差 × (1 - t)」だけ遠いオーバーレイを上下左右にずらす
                    (_late_shift_update。GPU を使わない平行移動で、描き直した結果と一致する)。前後 (拡大縮小) は絵のまま。
                    新しい絵を渡しても、SteamVR へのコピー (こちらの GL に積まれ、高負荷では遅れる) の後ろのフェンスが終わるまで
                    ずらしの基準は前の絵のまま (HUD_LATE_SHIFT_WAIT_COPY)。すぐ切り替えると渡すたびに小さく跳ぶ。
  入力: Quaternion / ピボット補正 (PivotCalibrator) / Throttle (リミッター付き) / VirtualDPad / Joystick

■ HUD の信号 (通知の段の 'on' や 'color_rules' に書く名前)
    'vbtn:番号'  vJoy に出したボタン (Joystick が device.set_button を見張って自動で集める)
    'sig:always' 'sig:font_test' 'sig:cruise' 'sig:left_app_menu' 'sig:pov_mode' 'sig:cece27'
    'sig:throttle_over_limit' 'sig:stick_grab' 'sig:throttle_grab'
  新しい信号は Joystick.update() の self.hud.update_hud_state(signals={...}) に足す。
  通知の段は「段を作る関数」(hud_row_bmark / hud_row_cruise / hud_rows_font_test) で作り、HUD_NOTICE_ROWS の順に並ぶ。
  毎回変わる文字は部品の 'text_fn' (例 hud_text_cruise_power) が values={...} から作る。'reserve' で幅を固定できる。

■ 座標
    シート座標 (TrackingUniverseSeated): x 右+, y 上+, z 手前+ [m]。板の px は 左上原点・右+・下+。
    テクスチャの上下の並びはバックエンドが決める (OpenGL: メモリの1行目 = 絵の下端, HudGfxOpenGL.FLIP_Y)。
    HudPlateOverlay は板の px (左上原点) だけで考え、GPU は HudGfx のメソッドだけで使う (D3D11 を足す準備)。

■ テスト
    実機なしでも、openvr / glfw / OpenGL を偽物に差し替えて HudPlateOverlay を動かせる
    (素材テクスチャの差分更新が、毎回全部描き直した結果と1ピクセルも違わないこと、などを確かめる)。
"""
import os
import re
import json
import threading
import atexit
import math
import time
from collections import deque
from PIL import Image, ImageDraw, ImageFont
import openvr
try:
    import msvcrt          # Windows: コンソールのキー入力(Cキー)でピボット計測を起動
except ImportError:
    msvcrt = None

from steam_vr_wheel.pyvjoy.vjoydevice import (
    HID_USAGE_X, HID_USAGE_Y, HID_USAGE_Z,
    HID_USAGE_RX, HID_USAGE_RY, HID_USAGE_RZ
)
from steam_vr_wheel._virtualpad import VirtualPad, RightTrackpadAxisDisablerMixin, LeftTrackpadAxisDisablerMixin


# ==============================================================================
# HUD-SWAP: 解決済み。原因は軸の「呼び名」の取り違え (下の _stick_outputs を参照)。
# 計算側の名前を直したので、HUDの入れ替えは不要になった (既定 False)。
# ==============================================================================
HUD_SWAP_YAW_ROLL = False

# スティック(右コントローラー)の姿勢の扱い
JOY_LEGACY_SCALING = False          # True: 旧計算(角度×sin(θ/2))に戻す。新旧の比較用
JOY_ALIGN_TO_GRAB_HEADING = True   # つかんだ瞬間のコントローラーの向きに軸をそろえる (プレイエリアの向きに依存しない)

# ==============================================================================
# システム名とバージョン ― 起動時にコンソール (CMD) へ表示。HUD は起動時に中央へ大きく出して消し (HUD_SPLASH_*)、
#   小さなバージョン表記を通知の段 (Bマーク) の数段上 = HUD の右上の端に常に出す (HUD_VERSION_*)
#   変更を配るたびに APP_VERSION を上げる (他の LLM・チャットで作業したときも上げること)。
#   HUD は Hornet フォント (英数字のみ) で描くので、英数字と記号だけで書く。
# ==============================================================================
APP_NAME = 'SteamVR Virtual Cockpit'       # システム名 (steam-vr-wheel を元にした操縦桿 + スロットル + HUD)。
                                           #   SACC が設計の元。仮想の物理スイッチを押すような仕組みは (今のところ) 無い
APP_VERSION = '0.1.13'                     # このプログラムの版 (変更を配るたびに上げる)
APP_BASE_VERSION = '2.5.4a'                # 元にした steam-vr-wheel の版


def app_version_text():
    """'SteamVR Virtual Cockpit v0.1.0 (steam-vr-wheel 2.5.4a)' のような1行 (コンソール用)。"""
    return '{} v{} (steam-vr-wheel {})'.format(APP_NAME, APP_VERSION, APP_BASE_VERSION)


def app_version_short():
    """'V0.1.1' (HUD の右上の表記用。システム名は起動時の表示にだけ出す)。"""
    return 'V{}'.format(APP_VERSION)

# ==============================================================================
# [CONFIG] HUD ユーザー設定 ― ユーザーが触る変数はここに集めてある ("# [CONFIG]" で検索)
# ==============================================================================
# 後でまとめて設定ファイル(throttle_pivot.json のようなもの)に移す予定の変数には、すべて [CONFIG] を付けてある。
# 座標の約束: x = 右が+ / y = 上が+ / z = 手前が+ (SteamVRのシート座標, 単位はメートル)。
#             位置を (右, 上) で書く変数は、右と上が+、メートルは HUD_SCALE=1.0 のときの値。

# --- HUD板(1枚の板)の位置と大きさ -------------------------------------------------
# 基準点 = 下の「操作インジゲータ」「通知インジゲータ」の位置を測る原点。z が板の奥行き位置 (頭からの距離)。
HUD_PLATE_POS = (0.02, -0.13, -0.55)       # [CONFIG] 基準点 (x, y, z) [m]。y を上げると HUD 全体が上へ (前回 -0.225 は低すぎた)
HUD_SCALE = 0.85                            # [CONFIG] HUD全体の大きさの倍率 (基準点を中心に、部品も間隔もまとめて拡大縮小)
HUD_METERS_PER_PIXEL = 0.12 / 512.0        # [CONFIG] 1px の実寸 [m] (HUD_SCALE=1.0 のとき)
HUD_PLATE_SIZE_M = None                    # [CONFIG] 板(窓)の大きさ (幅, 高さ)[m]。None = 中身に合わせて自動。数値にすると窓の外ははみ出さず切れる
HUD_PLATE_MARGIN_PX = 48                   # [CONFIG] 窓の大きさが自動のとき、中身の周囲に足す余白 [px]。奥行き表示で絵が動ける範囲 (窓の外は切れる)
# --- 画質 (解像度となめらかさ) ---------------------------------------------------------
# HUD は3段階で描く: 内部の絵 (HUD_RENDER_SCALE 倍の細かさ) → 縮小・拡大して出力テクスチャへ → SteamVR が画面へ。
# 縮小するときはミップマップ (前もって作った 1/2, 1/4... の絵) を使うので、小さく描いてもガビガビ・ちらつきが出にくい。
HUD_RENDER_SCALE = 1.5                     # [CONFIG] 内部の絵の細かさ。1.0 = 以前と同じ / 1.5 / 2.0 = 縦横2倍 (文字や線がなめらか)。
                                           #          上げるほど CPU の仕事が増える (スティックを動かしている間、1フレームあたり
                                           #          1.0 で約2ms / 1.5 で約4ms / 2.0 で約7ms の目安。操縦の反応が重くなったら下げる)
                                           #          px で書く設定 (段の高さなど) は 1.0 のときの値のままでよい (自動で掛ける)
HUD_TEXTURE_SCALE = None                   # [CONFIG] SteamVR に渡すテクスチャの解像度。None = 自動 (ヘッドセットの画素の細かさに合わせる)
                                           #          数値なら 1px(HUD_RENDER_SCALE=1.0 のとき) あたりの倍率 (1.0 = 以前の 1.0 と同じ)
HUD_TEXTURE_OVERSAMPLE = 2.0               # [CONFIG] 自動のときの余裕。必要な画素の何倍にするか。ぼやけて見えるなら上げる (2.0～3.0)
HUD_MIPMAP_MAX_LEVEL = 1                   # [CONFIG] 縮小用の絵を何段まで使うか。1 = 1/2 まで (くっきり) / 2 = 1/4 まで / 0 = 使わない (ガビガビ)
HUD_OPACITY = 0.85                         # [CONFIG] (AC風テスト。元は 0.65) HUD (線・文字・記号) の不透明度。SACC 風に少し透かす。0.8～1.0
                                           #          薄板 (HUD_PANEL_ALPHA) とデバッグ用の縦線は、この値では薄くならない
HUD_SOFTNESS = 0.15                         # [CONFIG] 縮小したときのやわらかさ。0 = いちばんくっきり / 0.25 = 少しやわらか / 0.5 = やわらか
                                           #          (小さく見えるほど自動でなめらかになる。その上に足すぼかしの量)
HUD_DEBUG_EDGE_PX = 8                      # [CONFIG] デバッグ用: 板(表示枠)の左右の端に描く縦線の太さ [px]。0 = 描かない
HUD_DEBUG_EDGE_COLOR = (24, 24, 24, 255)   # [CONFIG] その縦線の色 (r, g, b, a) 黒～黒に近い灰色
HUD_DEBUG_EDGE_INNER_COLOR = (96, 96, 96, 255)   # [CONFIG] 縦線のすぐ内側に足す細い線 (太さは半分) の色。None = 描かない
HUD_MAX_FPS = 120.0                        # [CONFIG] HUD を描き直す最大回数 [回/秒] (画面の更新が分からないときの上限)
HUD_OVERLAY_SORT_ORDER = 1000000            # [CONFIG] HUD の描画順の番号。大きいほど他のオーバーレイより上に描かれる。
                                           #          他のオーバーレイに隠れるなら、さらに大きくする (最大 4294967294)
HUD_THREADED = True                        # [CONFIG] True = HUD を専用の処理(スレッド)で、画面の更新(vsync)ごとに1回描く。
                                           #          操縦の処理のタイミングに左右されないので、頭を動かしたときのかくつきが減る
HUD_RENDER_AFTER_VSYNC_SEC = 0.001         # [CONFIG] vsync の何秒後に描き始めるか (専用スレッドのとき)

# --- 色 (下の通知の段でも使うので、先に定義しておく) -------------------------------------
HUD_COLOR_GREEN = (130, 255, 180, 255)      # [CONFIG] 通常のHUDの緑 (AC風テスト: ミント。元は (0, 255, 42, 255))
HUD_COLOR_YELLOW = (221, 204, 52, 255)     # [CONFIG] 黄色 (Bmark.png と同じ色)
HUD_BAR_COLOR_NORMAL = (130, 255, 180)     # [CONFIG] (AC風テスト。元は None) スロットルバーの通常色 (r, g, b)。None = throttlebar_pixel.png の色
HUD_BAR_COLOR_YELLOW = (206, 206, 39)      # [CONFIG] スロットルバーが黄色のときの色 (#CECE27)
HUD_BAR_YELLOW_WHEN = ['sig:cece27', 'sig:throttle_over_limit']   # [CONFIG] バーを黄色にする条件 (信号の名前のリスト。どれか1つで黄色)

# --- 操作インジゲータ (スロットルゲージ + ボックス + 十字 + yaw線) -----------------------
HUD_INDICATOR_OFFSET = (-0.13, -0.035)     # [CONFIG] 中心の位置 (基準点から 右, 上) [m]
HUD_INDICATOR_PANEL_PAD_PX = 12            # [CONFIG] 操作インジゲータの薄板の、部品の周りの余白 [px] (通知の段は HUD_PANEL_MARGIN_PX)

# --- デバッグログ (操作インジゲータの上、左揃え。SACC のログ表示のようなもの) -----------------------
# コンソール (CMD) に print した文字を、そのまま HUD にも出す (コンソールの表示はログとして残る)。
# 新しい行ほど下 (操作インジゲータのすぐ上)。古い行は上へ押し出され、HUD_LOG_HOLD_SEC で消える。
# Hornet フォントは大文字だけで '[' ']' なども無い。Hornet に無い文字は HUD_LOG_FONT_JP で描く。
# 英数字は HUD_LOG_FONT (Hornet)、日本語などは HUD_LOG_FONT_JP (Windows の日本語フォント) で描く。
# コンソールの L キー (コマンド 'hud_log_toggle') でログの行を隠す / 出す。プログラムからは hud_log('文字')。
HUD_LOG_ENABLED = True                     # [CONFIG] HUD にデバッグログを出すか
HUD_LOG_CAPTURE_PRINT = True               # [CONFIG] True = print した文字を全部 HUD にも出す / False = hud_log() で送ったものだけ
HUD_LOG_CAPTURE_STDERR = False             # [CONFIG] エラーの出力 (Python のエラーの詳細など) も HUD に出す
HUD_LOG_LINES = None                       # [CONFIG] 表示する行数。None = 自動 (上端がバージョン表記の高さを越えない数)。
                                           #   この高さの場所を最初から取っておく (行が増えても板の大きさは変わらない)
HUD_LOG_WIDTH_PX = None                    # [CONFIG] ログの幅 [px] (HUD_RENDER_SCALE=1.0 のとき)。長い行はこの幅で折り返す。
                                           #   None = 自動 (左端から通知の列の手前まで)
HUD_LOG_FONT_PX = 30                       # [CONFIG] 文字の大きさ [px] (同)。小さいと実機では読めない (22 は読めなかった)
HUD_LOG_LINE_PITCH = 1.25                  # [CONFIG] 行の間隔 (文字の大きさの何倍)
HUD_LOG_LARGE_SCALE = 1.5                  # [CONFIG] 「大きく」表示 (L キーで 普通 → 大きく → 隠す) の文字の倍率。
                                           #   場所は普通と同じ (行数が減る)。読みたいときだけ大きくする
HUD_LOG_OPACITY = 1.0                      # [CONFIG] ログの文字の不透明度 (HUD_OPACITY の代わり。小さい文字は透かすと読めない)
HUD_LOG_GLOW = False                       # [CONFIG] ログの文字ににじみ (HUD_GLOW_* / HUD_SOFTEN_PX) を付けるか。小さい文字はぼやけるので False
HUD_LOG_PANEL_ALPHA = 0.45                 # [CONFIG] ログの裏の薄板の濃さ (HUD_PANEL_ALPHA の代わり。明るい景色の上でも読めるよう濃いめ)
HUD_LOG_GAP_PX = 10                        # [CONFIG] 操作インジゲータ (の薄板) とのすき間 [px]
HUD_LOG_HOLD_SEC = 15.0                    # [CONFIG] 1行を出しておく秒数。0 = 消さない (新しい行に押し出されるまで残る)
HUD_LOG_WRAP_MAX = 6                       # [CONFIG] 長い1回分の表示を何行まで折り返すか (超えた分は '...' で切る。0.1.12 までは 4)
HUD_LOG_SHORTEN = True                     # [CONFIG] (0.1.13) HUD に出すときだけ、括弧 () （） の中の説明を省いて短くする。コンソールは全文のまま
HUD_LOG_FONT = 'hornet_bold'               # [CONFIG] 英数字のフォント (HUD_FONT_FILES の名前)
HUD_LOG_FONT_JP = 'jp'                     # [CONFIG] 日本語などのフォント (HUD_FONT_FILES の名前)
HUD_LOG_JP_SCALE = 0.95                    # [CONFIG] 日本語の文字の大きさの倍率 (英数字と高さが合わなければ変える)
HUD_LOG_COLOR = (130, 255, 180, 255)        # [CONFIG] 通常の文字の色 (AC風テスト。元は (0, 255, 42, 255))
HUD_LOG_COLOR_RULES = [                    # [CONFIG] この文字を含む行はこの色 (上から順に最初に合ったもの)
    ('Error', (255, 90, 60, 255)),
    ('Warning', (221, 204, 52, 255)),
]
HUD_LOG_PANEL = True                       # [CONFIG] 文字の裏に薄板 (HUD_PANEL_*) を敷く (HUD_PANEL_ENABLED が True のとき)
HUD_LOG_START_MODE = 'normal'              # [CONFIG] 起動時のログの表示: 'normal' (普通) / 'large' (大きく) / 'hidden' (隠す)。L キーで順に切り替え

# --- バージョン表記 (通知の段の数段上 = HUD の右上の端。これより上には今のところ何も置かない) --------------
HUD_VERSION_SHOW = True                    # [CONFIG] 出すか
HUD_VERSION_ROWS_ABOVE = 5.0               # [CONFIG] (実機で 5 に決めた) 通知の1段目 (Bマーク) の上端から、何段ぶん上に置くか (段の高さ + すき間 を1段)
HUD_VERSION_ALIGN = 'right'                # [CONFIG] 'right' = HUD の右端に右揃え (いちばん右まで出ている部品の右端) /
                                           #   'notice' = 通知の列の揃え (HUD_NOTICE_ALIGN) に合わせる
HUD_VERSION_FONT_PX = 34                   # [CONFIG] 文字の大きさ [px] ('V0.1.1' だけなので大きめ)
HUD_VERSION_COLOR = (130, 255, 180, 255)    # [CONFIG] (AC風テスト。元は (0, 255, 42, 255))
HUD_VERSION_PANEL = True                   # [CONFIG] 裏に薄板を敷く

# --- 起動時の表示 (HUD の中央に大きくシステム名とバージョン。しばらくして消える) --------------------------
HUD_SPLASH_SEC = 5.0                       # [CONFIG] 出しておく秒数 (消える時間を含む)。0 = 出さない。コマンド 'hud_splash' でもう一度出せる
HUD_SPLASH_FADE_SEC = 1.0                  # [CONFIG] 最後の何秒で薄くしながら消すか
HUD_SPLASH_OFFSET = None                   # [CONFIG] 中心の位置 (基準点から 右, 上) [m]。None = 自動 (板の左右の真ん中、
                                           #   上下はバージョン表記の下～通知の1段目の上の空き = 他の部品と重ならない所。ログは隠れる)
HUD_SPLASH_TITLE_PX = 84                   # [CONFIG] システム名の大きさ [px]
HUD_SPLASH_SUB_PX = 34                     # [CONFIG] その下のバージョンの行の大きさ [px]
HUD_SPLASH_COLOR = (130, 255, 180, 255)     # [CONFIG] (AC風テスト。元は (0, 255, 42, 255))
HUD_SPLASH_OPACITY = 1.0                   # [CONFIG] 文字の不透明度 (HUD_OPACITY の代わり。見やすさ優先で 1.0)
HUD_SPLASH_PANEL_ALPHA = 0.75              # [CONFIG] 裏の板の濃さ。後ろの HUD の部品や明るい景色を隠して読みやすくする。0 = 板なし
HUD_SPLASH_HIDE_LOG = True                 # [CONFIG] 出している間はデバッグログを隠す (重なるため。ログの行は残っていて、消えた後に出る)

# --- システム通知インジゲータ (一番上の段 = Bマーク。下へ段が増える) ------------------------
HUD_NOTICE_OFFSET = (0.13, 0.035)          # [CONFIG] 1段目(いちばん上)の中心の位置 (基準点から 右, 上) [m]
HUD_NOTICE_ROW_GAP_PX = 10                 # [CONFIG] 段と段のすき間 [px]
HUD_NOTICE_ROW_HEIGHT_PX = 64              # [CONFIG] 通知の段の高さ [px] (Bマークも文字の段もこの高さにそろえる)。段ごとの 'height' で上書きできる
HUD_NOTICE_ALIGN = 'left'                  # [CONFIG] 段の左右の揃え: 'left' (SACC と同じ) / 'center' / 'right'
HUD_NOTICE_PART_GAP_PX = 14                # [CONFIG] 1つの段の中で、部品 (例: 枠付き CRUISE と 55%) の間のすき間 [px]

# 通知の段の定義 ―― 段は1つずつ「段を作る関数」(hud_row_...) で作り、HUD_NOTICE_ROWS に並べた順に上から出す。
#   中身を書き換えるときはその関数だけ直す。並び替えは HUD_NOTICE_ROWS の中の順番を入れ替えるだけ。
#   新しい段を作るときは、下の関数をまねて hud_row_なにか() を作り、HUD_NOTICE_ROWS に足す。
#
# 段 (dict) に書けるキー:
#   'id'          名前 (自由。段ごとに別の名前にする)
#   'on'          この段を出す条件。下の「信号」の名前のリスト (どれか1つでも ON なら出る)
#   'hold_sec'    条件が消えたあとも残す秒数。0 = 押している間だけ。既定 0
#   'color'       通常の色 (文字・recolor画像用)。既定は緑 HUD_COLOR_GREEN
#   'color_rules' 色を変える条件。[{'when': [信号...], 'color': 色}, ...] 上から順に最初に合ったものを使う
#   'panel'       この段に半透明の薄板を付けるか。既定 True (HUD_PANEL_ENABLED が True のとき)
#   'height'      この段だけ高さ [px] を変える (既定 HUD_NOTICE_ROW_HEIGHT_PX)
#   'space_after_px' この段の下に足す空き [px] (段のすき間とは別)。既定 0
#   'parts'       段の中身。左から順に並べる部品のリスト (間は HUD_NOTICE_PART_GAP_PX)。部品に書けるキー:
#       'image'      画像ファイル名 (media/hotas_sacc/ か media/)。'recolor': True で 'color' の色に塗る
#       'text'       文字。{btn:名前} は仮想ボタン記号 (HUD_BUTTON_GLYPHS)。'font' 'size' 'btn_scale' も使える
#       'text_fn'    文字を毎回作る関数 (下の hud_text_... のようなもの)。値の辞書を受け取り、文字列を返す
#       'reserve'    この文字列が入るだけの幅を最初から取っておく (例 '100%')。数字が変わっても幅が増減しない
#       'align'      'reserve' の幅の中での寄せ方: 'right' (既定) / 'left' / 'center'
#       'box'        True で部品全体を □ の枠で囲む (SACC の LIMIT のような表示)
#   ('parts' を書かずに 'image' や 'text' 'box' を段に直接書くと、部品1つの段になる)
#
# 信号の名前 ('on' や 'color_rules' に書く):
#   'sig:always'           いつも ON
#   'sig:font_test'        HUD_FONT_TEST が True の間 ON (確認用に段を出しておく)
#   'sig:cruise'           クルーズモード中 (CRUISE_MODE_ENABLED。今は予約)
#   'vbtn:22'              vJoy の仮想ボタン 22 番が押されている (番号は自由。出力した vJoy ボタンを自動で見張る)
#   'sig:left_app_menu'    左コントローラーのアプリメニュー
#   'sig:pov_mode'         十字キーモード中
#   'sig:cece27'           set_cece27(True) で入る状態
#   'sig:throttle_over_limit' スロットルがリミッターの制限値(80%)を超えている
#   'sig:stick_grab'       右グリップでスティックをつかんでいる
#   'sig:throttle_grab'    左グリップでスロットルをつかんでいる
# 'text_fn' が受け取る値 (Joystick.update() が毎フレーム渡す):
#   'throttle' 0.0～1.0 / 'cruise_power' 0.0～1.0 (CRUISE_MODE_Power。None ならスロットルの値) / 'cruise_center' True/False


def hud_text_cruise_power(v):
    """CRUISE の横に出す値。センタークルーズなら 'C'、それ以外は '55%' のような百分率。"""
    if v.get('cruise_center'):
        return 'C'
    p = v.get('cruise_power')
    if p is None:
        return '--%'
    return '{}%'.format(int(round(max(0.0, min(1.0, float(p))) * 100)))


def hud_row_bmark():
    """1段目: Bマーク (左コントローラーのアプリメニュー。離してから 1.5 秒残す)"""
    return {'id': 'B', 'image': 'Bmark.png', 'on': ['sig:left_app_menu'], 'hold_sec': 1.5,
            'space_after_px': HUD_NOTICE_ROW_HEIGHT_PX}     # SACC の BRAKE のように、下の段との間を1段分あける


def hud_row_cruise():
    """クルーズ表示: 枠付き CRUISE + 枠なしの値 (幅は '100%' 分を確保して右寄せ)"""
    return {'id': 'cruise', 'on': ['sig:cruise', 'sig:font_test'],
            'parts': [{'text': 'CRUISE', 'box': True},
                      {'text_fn': hud_text_cruise_power, 'reserve': '100%', 'align': 'right'}]}


HUD_CLOCK_ENABLED = True                   # [CONFIG] 通知の段に現在時刻 (PC の時計、時:分:秒) を出す。動画・CSV・ログと見比べる目印
HUD_CLOCK_FORMAT = '%H:%M:%S'              # [CONFIG] time.strftime の書式。Hornet は大文字・数字・':' '.' '-' は描ける
HUD_CLOCK_TENTHS = True                    # [CONFIG] (デバッグ用) 秒の後ろに 0.1 秒の桁を出す (動画と CSV を合わせるため)。
                                           #   文字が 1 秒に 10 回変わるので描き直しが 10 回/秒増える。普段使いでは False


def hud_text_clock(v):
    """現在時刻 (HUD_CLOCK_FORMAT)。秒が変わったときだけ文字が変わるので、描き直しは 1 秒に 1 回増えるだけ。"""
    now = time.time()
    t = time.strftime(HUD_CLOCK_FORMAT, time.localtime(now))
    if HUD_CLOCK_TENTHS:
        t += '.{}'.format(int((now % 1.0) * 10.0) % 10)
    return t


def hud_row_clock():
    """現在時刻の段 (いつも出す)。幅は '00:00:00' 分で固定。"""
    return {'id': 'clock', 'on': ['sig:always'],
            'parts': [{'text_fn': hud_text_clock, 'reserve': '00:00:00.0' if HUD_CLOCK_TENTHS else '00:00:00',
                       'align': 'left'}]}


def hud_rows_font_test():
    """フォント確認用の段 (HUD_FONT_TEST が True のときだけ出す)。"""
    on = ['sig:font_test']
    btn_h = int(round(HUD_NOTICE_ROW_HEIGHT_PX * 1.15))     # 記号は少し大きめ
    return [
        {'id': 'font_text', 'text': 'M 0.00  G 1.0', 'on': on},    # 枠なし文字 (今後使う予定)
        {'id': 'font_btn1', 'box': True, 'on': on, 'height': btn_h,
         'text': '{btn:A}{btn:B}{btn:X}{btn:Y}{btn:LB}{btn:RB}{btn:LT}{btn:RT}{btn:XBOX}{btn:MENU}{btn:VIEW}'},
        {'id': 'font_btn2', 'box': True, 'on': on, 'height': btn_h,
         'text': '{btn:DPAD}{btn:DPAD_UP}{btn:DPAD_RIGHT}{btn:DPAD_DOWN}{btn:DPAD_LEFT}'
                 '{btn:DPAD_UL}{btn:DPAD_UR}{btn:DPAD_DR}{btn:DPAD_DL}'},
        {'id': 'font_btn3', 'box': True, 'on': on, 'height': btn_h,
         'text': '{btn:STICK}{btn:STICK_UP}{btn:STICK_RIGHT}{btn:STICK_DOWN}{btn:STICK_LEFT}'
                 '{btn:STICK_UL}{btn:STICK_UR}{btn:STICK_DR}{btn:STICK_DL}{btn:LS}{btn:RS}',
         'color_rules': [{'when': ['sig:pov_mode'], 'color': HUD_COLOR_YELLOW}]},   # 十字キーモード中は黄色 (色ルールの確認)
    ]


# --- Q29-3 調査用: スティックと VirtualDPad の数値の段 (デバッグ版だけ) ---------------------
# 'text_fn' は values['dbg'] (Joystick._dpad_debug_values が作る辞書) を読む。Hornet は < > | # [ ] と小文字が無いので使わない。
DPAD_DEBUG_HUD = True                      # [CONFIG] 起動時に数値の段を出すか (P キーで出す / 隠す)
DPAD_DEBUG_HUD_HZ = 20.0                   # [CONFIG] 段の数字を書き換える回数 [回/秒]。多いほど細かいが HUD の描き直しが増える
DPAD_DEBUG_LOG = True                      # [CONFIG] VirtualDPad の方向が変わるたびに [DPAD] の1行をログ (コンソール + HUD) に出す
_DPAD_DIR_NAMES = {5: 'N', 8: 'U', 9: 'UR', 6: 'R', 3: 'DR', 2: 'D', 1: 'DL', 4: 'L', 7: 'UL'}


def _dbg_f(v, fmt='{:+.2f}'):
    try:
        return fmt.format(float(v))
    except Exception:
        return '--'


def hud_text_dbg_ls(v):
    """左スティックの生の値 (rAxis[0])。R = 中心からの距離。"""
    d = v.get('dbg') or {}
    return 'LS X {} Y {} R {}'.format(_dbg_f(d.get('lx')), _dbg_f(d.get('ly')), _dbg_f(d.get('lr'), '{:.2f}'))


def hud_text_dbg_rs(v):
    """右スティックの生の値 (rAxis[0]。VirtualDPad に入る値)。A = 角度 (右 0、上 +90、左 180、下 -90)。"""
    d = v.get('dbg') or {}
    return 'RS X {} Y {} R {} A {}'.format(_dbg_f(d.get('rx')), _dbg_f(d.get('ry')), _dbg_f(d.get('rr'), '{:.2f}'),
                                          _dbg_f(d.get('ra'), '{:+04.0f}'))


def hud_text_dbg_avg(v):
    """VirtualDPad が判定に使う 3 回平均の距離と角度。E = いちばん近い区画の境目までの角度。"""
    d = v.get('dbg') or {}
    return 'AVG R {} A {} E {}'.format(_dbg_f(d.get('dist'), '{:.2f}'), _dbg_f(d.get('ang'), '{:+06.1f}'),
                                       _dbg_f(d.get('edge'), '{:04.1f}'))


def hud_text_dbg_dir(v):
    """判定結果。TH = 今使っているしきい値 (中立なら入る 0.60、方向中なら出る 0.45)。POV / BTN = 出力の方式。"""
    d = v.get('dbg') or {}
    di = d.get('dir', 5)
    return 'DIR {} {} TH {} {} {}'.format(di, _DPAD_DIR_NAMES.get(di, '-'), _dbg_f(d.get('th'), '{:.2f}'),
                                          d.get('mode', '-'), d.get('out', '-'))


def hud_text_dbg_chg(v):
    """方向が変わった回数 (中立を含む) と、今の方向になってからの時間 [ms]。"""
    d = v.get('dbg') or {}
    return 'CHG {:04d} MS {:05d}'.format(int(d.get('chg', 0)) % 10000, min(99999, int(d.get('ms', 0))))


def hud_rows_dpad_debug():
    """数値の段 (左寄せ、幅は最大の文字列で固定)。'sig:dpad_debug' の間だけ出す。"""
    on = ['sig:dpad_debug']
    return [
        {'id': 'dbg_ls', 'on': on, 'parts': [{'text_fn': hud_text_dbg_ls, 'reserve': 'LS X -0.00 Y -0.00 R 0.00', 'align': 'left'}]},
        {'id': 'dbg_rs', 'on': on, 'parts': [{'text_fn': hud_text_dbg_rs, 'reserve': 'RS X -0.00 Y -0.00 R 0.00 A -180', 'align': 'left'}]},
        {'id': 'dbg_avg', 'on': on, 'parts': [{'text_fn': hud_text_dbg_avg, 'reserve': 'AVG R 0.00 A -180.0 E 22.5', 'align': 'left'}]},
        {'id': 'dbg_dir', 'on': on, 'parts': [{'text_fn': hud_text_dbg_dir, 'reserve': 'DIR 5 UR TH 0.00 POV 31500', 'align': 'left'}]},
        {'id': 'dbg_chg', 'on': on, 'parts': [{'text_fn': hud_text_dbg_chg, 'reserve': 'CHG 0000 MS 00000', 'align': 'left'}]},
    ]


HUD_FONT_TEST = True                       # [CONFIG] フォント確認用の段を出す (確認が終わったら False)
HUD_NOTICE_ROWS = [                        # [CONFIG] 上から並べる順番
    hud_row_bmark(),
    hud_row_cruise(),
] + ([hud_row_clock()] if HUD_CLOCK_ENABLED else []) + hud_rows_dpad_debug() + (hud_rows_font_test() if HUD_FONT_TEST else [])   # 数値の段をアイコンの段より上に (DPAD2)

# --- 半透明の薄板 (HUD表示部分だけの裏に敷く。ゲーム画面は隠さない) -----------------------
HUD_PANEL_ENABLED = True                   # [CONFIG] 薄板を付けるか
HUD_PANEL_COLOR = (0, 0, 0)                # [CONFIG] 薄板の色 (黒〜灰色。黒以外だと縁の色がずれることがある)
HUD_PANEL_ALPHA = 0.35                     # [CONFIG] 薄板の濃さ 0.0(透明)〜1.0。0.2 では明るい景色で薄すぎたので、
                                           #   ログ (HUD_LOG_PANEL_ALPHA 0.45) とロゴ (HUD_SPLASH_PANEL_ALPHA 0.75) に寄せて 0.35
HUD_PANEL_MARGIN_PX = 3                    # [CONFIG] 表示部分の周囲に足す幅 [px]
HUD_PANEL_KNOCKOUT = True                  # [CONFIG] 線・文字の下だけ薄板をくり抜く (薄板の灰色と線の緑を混ぜない)。
                                           #   半透明の緑を灰色の上に重ねると、明るい景色の上で薄い灰緑になって読みにくいため。
                                           #   線・文字は景色の上に直接、薄板はその周りだけに見える。False = 前と同じ (上に重ねる)

# --- 奥行き表示 (視差) ―― 戦闘機のHUD / ホログラフィックサイトのような見え方 ------------------
# HUD_DEPTH_MODE で見せ方を選ぶ (3種類。実行中もコンソールの F キー / set_mode() で切り替えられる):
#   'fakefar' (通常・既定) HUD のオーバーレイを板の少し奥 (HUD_FAKEFAR_DIST_M) に置き、そこから 20m 先に見えるよう描き直す。
#             SteamVR 2.17 以降 + Quest などのストリーミングでは、オーバーレイの重なりが描画順の番号ではなく距離で決まる
#             (SteamVR の不具合)。本当に遠く置くと、それより手前の他のオーバーレイ (ゲームのメニュー画面など) に隠れる。
#             なので隠れない距離まで手前に置く。代わりに、頭を動かしたときの揺れが少し残る。
#   'far'     (最高の見え方) HUD を本当に HUD_DEPTH_DISTANCE_M 奥に置く。記号の位置は SteamVR が景色と同じように合わせるので
#             揺れない (SACC と同じ考え方)。他のオーバーレイに隠されない環境向け (直結のヘッドセット / SteamVR 2.16 以前)。
#   'plate'   (互換) 板に描く絵を毎フレーム描き直して、板の向こうにあるように見せる (最初の方式)。
#   'fakefar' と 'far' で描き直すのは「板(窓)から見える範囲の切り抜き」(SACC のステンシルの代わり) と、'fakefar' の位置合わせ。
#   板の位置には、デバッグ用の縦線だけの小さなオーバーレイを置く。
# 以下は 'plate' のときの説明 ('far' でも見え方は同じ):
#   ・上下左右: 頭を動かすと、奥にあるぶんだけ板の上でずれて見える (20m なら頭とほぼ一緒に動く = 照準器)
#   ・前後    : HUD_DEPTH_KEEP_SIZE = True なら、板に近づいても離れても見た目の大きさは変わらない
#   ・板(窓)の外へ出た部分は切れて見えない (窓の大きさは HUD_PLATE_SIZE_M / HUD_PLATE_MARGIN_PX)
# 基準の目の位置 = HUD_PLATE_POS + HUD_DEPTH_EYE_OFFSET (固定。起動のたびに変わらない)。
#   目がこの位置にあるとき、奥行きの値に関係なく絵は設計どおりの位置・大きさに見える。
#   None (既定) = シート座標の原点 (着座位置をリセットしたときの頭の位置)。HUD_PLATE_POS を動かしても自動で合う。
#   コンソールで Hキー → 今の頭の位置を表示してこのセッションだけ使う (固定するなら値を下に書く)
HUD_DEPTH_ENABLED = True                   # [CONFIG] False = 頭の位置を見ない (絵は板に固定)
HUD_DEPTH_MODE = 'fakefar'                 # [CONFIG] 'fakefar' (通常) / 'far' (最高の見え方。隠されない環境向け) / 'plate' (互換)
HUD_FAKEFAR_DIST_M = 0.56                  # [CONFIG] 'fakefar' のオーバーレイを板から何 m 奥に置くか。他のオーバーレイに隠れない範囲で大きいほど揺れが減る
                                           #   揺れの大きさ (plate = 100%): 0.57m ≒ 48% / 1.0m ≒ 34% / 2.0m ≒ 19% / far = 0%
                                           #   (起動時と切り替え時に、コンソールへ今の割合を表示する)
HUD_FAR_WINDOW_CLIP = True                 # [CONFIG] 'far' で板(窓)の形に切り抜くか。True (既定) = SACC のようにガラスの形で切り抜く
                                           #   (頭の位置は切り抜きにだけ使う。'far' では絵の拡大・ずらしはしない)。
                                           #   False = 切り抜かない (頭の位置を一切使わない。HUD は窓の外にも見える)
HUD_DEPTH_DISTANCE_M = 20.0                # [CONFIG] 奥行きの距離 [m] (板の面から奥へ)。HUD全体で1つ。0 = 板に貼り付き
HUD_DEPTH_KEEP_SIZE = True                 # [CONFIG] ('plate' のみ) True = 前後に動いても見た目の大きさ一定 / False = 近づくと大きく見える
                                           #          ('far' / 'fakefar' の虚像は空間に固定。20m 先なら前後に 20cm 動いても大きさは 1% しか変わらない)
HUD_DEPTH_EYE_OFFSET = None                # [CONFIG] 基準の目の位置 = HUD基準点から (右, 上, 手前) [m]。None = シート座標の原点
HUD_DEPTH_CLAMP_NEAR = False               # [CONFIG] 目が板を越えたとき (板を裏から見たとき):
                                           #   False = 'fakefar' / 'far' は HUD を消す (SACC と同じ)。'plate' は絵を止める
                                           #   True  = 'fakefar' / 'far' は前の絵のまま止める。'plate' は最小距離 15cm に押さえて計算を続ける
HUD_DEPTH_PREDICT_SEC = None               # [CONFIG] 頭の位置の先読み [秒]。None = 自動 (次に画面に出る瞬間の頭の位置を SteamVR に予測させる)
HUD_POSE_SOURCE = 'display'                # [CONFIG] HUD を描くときの頭の位置:
                                           #   'display' = (既定。'fakefar' / 'far' のとき) 'far' (本当に遠くに置く) と同じ見え方を目指す。
                                           #               ゲームの姿勢は使わず、画面の更新 (vsync) ごとに、SteamVR が画面を作る直前
                                           #               (次の vsync の HUD_DISPLAY_RENDER_LEAD_SEC 前) に、最新の頭の位置の予測で描く。
                                           #               ゲームの FPS に引っ張られない。'plate' では 'predict' と同じ
                                           #   'hybrid'  = (既定。'fakefar' / 'far' のとき) 2つの頭の位置を組み合わせる。
                                           #               SteamVR は、ゲームの画面は「ゲームが描いたときの頭の位置」のまま (向きだけ補正) 出すが、
                                           #               オーバーレイは画面を作るたびに「最新の頭の位置」で置き直す (ゲームより速い)。
                                           #               なので HUD の「見える方向」は今画面に出ているゲームのフレームの頭の位置から、
                                           #               「オーバーレイの上のどこに描くか」は最新の頭の位置 (予測) から計算し、
                                           #               画面の更新 (vsync) ごとに描き直す。FPS が低くても、ダッシュボードの下でも、
                                           #               HUD がゲームの画面 (コックピット) と同じように見える。'plate' では 'game' と同じ
                                           #   'game'    = ゲームがその画面を描いたときと同じ頭の位置 (SteamVR の GetLastPoses)。
                                           #               ゲームのフレームが変わるたびに描き直すので、ゲームの FPS が低くても
                                           #               HUD とコックピットがずれにくい (SACC のようにゲームの中で描いたのに近い)
                                           #   'predict' = 次に画面に出る瞬間の頭の位置を予測して、画面の更新ごとに描く (前回まで)
                                           #   'game' で姿勢が取れない・止まっているときは、自動で 'predict' を使う (コンソールに表示)
HUD_DISPLAY_CONTINUOUS = True              # [CONFIG] 'display' のとき: True = vsync を待たず HUD_DISPLAY_INTERVAL_SEC ごとに描いて渡し続ける
                                           #   (SteamVR がいつ画面を作っても、最大その間隔ぶんしか古くない絵が使われる。CPU の仕事は増える)
                                           #   False = vsync ごとに1回、次の vsync の HUD_DISPLAY_RENDER_LEAD_SEC 前に描く
HUD_DISPLAY_PREDICT_SEC = None             # [CONFIG] 描き続けるときの先読み [秒]。vsync には合わせず、常に「今からこの時間先」を予測する
                                           #   (vsync に合わせると、狙う時刻が vsync ごとに跳び、疑似 far の位置合わせが段差になって見えるため)。
                                           #   None = 自動 (1フレームの半分 + vsync から光るまで)。[ / ] キーの調整もこれに足される
HUD_DISPLAY_LATENCY_COMP = False           # [CONFIG] 描き続けるとき、「頭の位置を読んでから SteamVR に渡し終わるまで」の実際の時間を測り、
                                           #   そのぶん先読みを長くする。高負荷では遅れが大きくばらつき、先読みが伸びて揺れが増えたので既定は False。
                                           #   HUD_LATE_SHIFT が効いているときは使わない (遅れはずらしで直すため)
HUD_LATE_SHIFT = True                      # [CONFIG] 'fakefar' で描き続けるとき、GPU 待ちで絵が遅れても、絵を作ったときの頭の位置と最新の予測の差だけ
                                           #   遠いオーバーレイを上下左右にずらして合わせる (位置の変更だけなので GPU を使わず、ゲームの負荷に引っ張られない)。
                                           #   GPU を待つ間も約 1ms ごとにずらし直す。前後 (拡大縮小) は絵のまま。おかしければ False
HUD_LATE_SHIFT_WAIT_COPY = True            # [CONFIG] 新しい絵を渡したあと、SteamVR へのコピーが GPU で終わるまで、ずらしの基準を前の絵のままにする。
                                           #   (すぐ切り替えると、まだ前の絵が見えている間に新しい絵用のずらしになり、渡すたびに小さく跳ぶ。高負荷ほど目立つ)
HUD_LATE_SHIFT_SWITCH_VSYNC = 0            # [CONFIG] コピーが終わってから、さらに何回 vsync を待ってずらしの基準を切り替えるか (0/1/2/3)。
                                           #   SteamVR が新しい絵を使い始めるのが、コピー完了より遅いときに合わせる。
                                           #   Quest 3 + Virtual Desktop の実機では 0 が最も揺れにくい (3 は頭を止めた後ゆっくり戻る = 待ちすぎ)。
                                           #   実行中はコンソールの V キーで 0→1→2→3→0 と切り替えて揺れの少ない値を探す
HUD_LATE_SHIFT_VSYNC_TARGET = True         # [CONFIG] ずらしの頭の位置の予測を「SteamVR が次に合成する画面が光る時刻」に合わせる。
                                           #   位置 (ずらし) は毎フレーム SteamVR が最新の値を読むので、絵と違って vsync に合わせても段差にならない。
                                           #   False = 絵と同じ「常に一定時間先」。実行中はコンソールの T キーで切り替え
HUD_LATE_SHIFT_RUNNING_START_SEC = 0.003   # [CONFIG] SteamVR が vsync の何秒前に合成を始めるか (この時刻を過ぎたら、その次の画面を狙う)
HUD_LATE_SHIFT_MAX_M = 0.05                # [CONFIG] ずらす量の上限 [m] (予測が飛んだときに HUD が大きく跳ばないため)
HUD_FIXED_REF = False                      # [CONFIG] (検証用 0.1.13) True = 'fakefar' の絵を基準の目 E0 から見た形 (設計どおり) で描き、
                                           #   頭の動きはすべてずらしで直す (絵に頭の位置を焼き込まない)。B キーで切り替え。
                                           #   ずらし (HUD_LATE_SHIFT) が入のときだけ効く。窓の切り抜きも基準の目のまま (端が少しずれて見える)
HUD_FIXED_REF_SHIFT_MAX_M = 0.30           # [CONFIG] HUD_FIXED_REF のときのずらす量の上限 [m] (頭が基準の目から離れたぶんだけずらすので大きめ)
HUD_FIXED_REF_FOLLOW_Z = True              # [CONFIG] HUD_FIXED_REF のとき、頭の前後の動きに合わせてオーバーレイも前後に動かす
                                           #   (見た目の大きさが変わらない = 20m 先の物と同じ)。板より手前には出さない
HUD_DEBUG_CROSSHAIR = True                 # [CONFIG] (検証用 0.1.13) 'fakefar' / 'far' で、基準の目の真正面 (HUD の中心) に十字線を描く。U キーで切り替え
HUD_DEBUG_CROSSHAIR_AT = 'eye'             # [CONFIG] 十字線の場所: 'eye' = 基準の目の真正面 (SACC の照準と同じ。景色の水平線に対して止まって見えるはずの点) /
                                           #   'plate' = HUD の基準点 (HUD_PLATE_POS。部品の並びの原点)
HUD_DEBUG_CROSSHAIR_COLOR = (255, 80, 255, 255)   # [CONFIG] 十字線の色 (HUD の色と見分けやすい紫)
HUD_DEBUG_CROSSHAIR_PX = 60                # [CONFIG] 十字線の腕の長さ [px] (HUD_RENDER_SCALE=1.0 のとき)
HUD_DEBUG_CROSSHAIR_WIDTH_PX = 3           # [CONFIG] 十字線の太さ [px] (同)
# --- HUD 揺れ調査用 (JIT1、デバッグ版だけ) ---
HUD_TEXTURE_FREEZE_HZ = 0.0                # [CONFIG] 0 = 通常。>0 = 'fakefar' の絵の描き直しをこの回数 [回/秒] までに絞る (ずらしはそのまま)。X キーで切り替え
HUD_TEXTURE_FREEZE_STEPS = [0.0, 240.0, 120.0, 80.0, 60.0, 40.0, 20.0, 10.0, 5.0, 1.0]   # [CONFIG] X キーで順に切り替える値
HUD_TEXTURE_FREEZE_SHIFT_MAX_M = 0.30      # [CONFIG] 絞っている間のずらす量の上限 [m] (絵が古いぶん、ずらす量が大きくなるため)
HUD_POSE_THREAD = False                    # [CONFIG] (検証用) 位置の計算を別スレッド ('hud_pose') で約 1ms ごとに回す。G キーで 切 → 姿勢だけ → 全部。
                                           #   False = 描く側で計算 (通常) / True ('姿勢だけ') = 頭の姿勢の予測だけ別スレッド /
                                           #   'full' ('全部') = 写し方 (視差・拡大縮小) とずらしも別スレッド。描く側は代入された値を読むだけ
HUD_POSE_THREAD_INTERVAL_SEC = 0.001       # [CONFIG] 別スレッドで計算する間隔 [秒]
HUD_POSE_THREAD_MAX_AGE_SEC = 0.02         # [CONFIG] これより古い計算結果は使わず、その場で読む (別スレッドが止まったときの保険)
HUD_JITTER_CSV_DIR = None                  # [CONFIG] 調査用 CSV を置くフォルダ。None = この .py と同じフォルダ。J キーで記録の開始 / 停止
HUD_JITTER_CSV_FLUSH_SEC = 0.5             # [CONFIG] CSV をファイルに書き出す間隔 [秒] (毎回書くと HUD の描画が遅れるため、ためてまとめて書く)
DEBUG_KEYMAP = [                           # [CONFIG] コンソールのキー → デバッグコマンド (Joystick.debug_command の名前)。
    ('h', 'hud_recenter'),                 #   大文字・小文字は区別しない。コマンドの一覧は Joystick.DEBUG_COMMANDS
    ('f', 'hud_cycle_mode'),
    ('s', 'hud_stats'),
    ('d', 'hud_diagnose'),
    ('v', 'hud_shift_switch_vsync'),
    ('t', 'hud_shift_vsync_target'),
    ('[', 'hud_predict_down'),
    (']', 'hud_predict_up'),
    ('\\', 'hud_predict_reset'),
    ('c', 'pivot_calibration'),
    ('l', 'hud_log_cycle'),
    ('p', 'dpad_debug'),                   # Q29-3 調査用 (デバッグ版だけ)
    ('o', 'dpad_log'),                     # Q29-3 調査用: [DPAD] の1行ログを出す / 止める
    ('k', 'hud_late_shift_toggle'),        # HUD 揺れ調査用 (JIT1)
    ('x', 'hud_texture_freeze'),           # HUD 揺れ調査用 (JIT1)
    ('j', 'hud_jitter_csv'),               # HUD 揺れ調査用 (JIT1)
    ('g', 'hud_pose_thread'),              # 検証用 (0.1.9)
    ('b', 'hud_fixed_ref'),                # 検証用 (0.1.13)
    ('u', 'hud_crosshair'),                # 検証用 (0.1.13)
]
HUD_GFX_BACKEND = 'opengl'                 # [CONFIG] 描画の裏方。今は 'opengl' だけ (D3D11 は予定。HudGfx を継承して足す)
HUD_THREAD_HIGH_PRIORITY = True            # [CONFIG] HUD の描画スレッドの優先度を上げる (Windows)。ワールド読み込みなど CPU が重いときの遅れ・跳びを減らす。
                                           #   さらに Python のスレッド切り替え間隔を 1ms にする (既定 5ms)。操縦の反応がおかしければ False
HUD_DISPLAY_INTERVAL_SEC = 0.002           # [CONFIG] 描き続けるときの間隔 [秒]。操縦の反応が重くなったら 0.003～0.004 に
HUD_OUTPUT_DOUBLE_BUFFER = True            # [CONFIG] 出力テクスチャを2枚にして交互に描いて渡す (SteamVR が読んでいる最中に描き換えないため)。
                                           #   GL エラーが出る・表示がおかしいときは False
HUD_DISPLAY_RENDER_LEAD_SEC = 0.004        # [CONFIG] 'display' のとき、次の vsync の何秒前に描くか。小さいほど新しい姿勢で描けるが、
                                           #   描画が間に合わないと1つ前の絵が出る (統計の「vsync 直前」が増えたら大きくする)。0.003～0.006
HUD_GAME_POSE_POLL_SEC = 0.002             # [CONFIG] 'game' のとき、ゲームの新しいフレームを確かめる間隔 [秒]
HUD_GAME_SYNC = True                       # [CONFIG] 'game' のとき、HUD を「そのゲームのフレームが画面に出るのと同じ vsync」に出す。
                                           #   HUD はすぐ描いておき、SteamVR に渡すのを、ゲームのフレームが出る直前の vsync の後まで待つ。
                                           #   (すぐ渡すと、まだ前のゲームの画面と一緒に出てしまうことがあり、それが揺れになる)
HUD_GAME_SYNC_DELAY_VSYNC = None           # [CONFIG] 待つ vsync の数。None = 自動 (ゲームの FPS から決める) / 0 = 待たない / 1, 2 ... = 手動
                                           #   自動で揺れが残るとき、統計の「待った vsync」を見て 1 か 2 を試す
HUD_GAME_SYNC_AFTER_VSYNC_SEC = 0.001      # [CONFIG] vsync の何秒後に渡すか
HUD_GAME_SYNC_RENDER_MARGIN_SEC = 0.002    # [CONFIG] 自動のとき: ゲームの1フレームの時間からこれを引いて、画面に出る vsync を見積もる
HUD_STATS_SEC = 0.0                        # [CONFIG] 描き直しが間に合っているかの統計を、この秒数ごとにコンソールへ表示。0 = 表示しない
                                           #          (実行中はコンソールの S キーで 5 秒ごとの表示を入/切できる)
HUD_STATS_LATE_MARGIN_SEC = 0.003          # [CONFIG] 統計: HUD を渡したのが次の vsync のこの秒数前より後なら「ぎりぎり」と数える
HUD_GAME_POSE_STALE_SEC = 2.0              # [CONFIG] ゲームの姿勢がこの秒数変わらなければ、ゲームがないとみなして予測に切り替える
HUD_DEPTH_PREDICT_EXTRA_SEC = 0.012        # [CONFIG] 自動の先読みに足す秒数。頭を振ると HUD が遅れてついて来るなら 0.011 (1フレーム) ずつ増やす。
                                           #          (Quest 3 + Virtual Desktop の実機で 0.012 に決めた。[ / ] キーで調整できる)
                                           #          逆に先へ行きすぎて揺れるなら減らす (マイナスも可)

# --- 左右の目で別々の絵 (立体視) ----------------------------------------------------------
# 左目用・右目用の絵を横に並べた1枚のテクスチャを作り、SteamVR に「左半分を左目、右半分を右目」で表示させる
# (オーバーレイの SideBySide_Parallel)。これで目の寄り具合も HUD_DEPTH_DISTANCE_M の距離に合い、本当に遠くに見える。
HUD_STEREO = True                          # [CONFIG] False = 両目に同じ絵 (以前の表示)
HUD_STEREO_IPD_M = None                    # [CONFIG] 目の間隔 [m]。None = SteamVR から取得 (取れなければ 0.063)
HUD_STEREO_SWAP = False                    # [CONFIG] 奥ではなく手前に飛び出して見える (左右が逆) なら True
HUD_STEREO_TEXEL_ASPECT = None             # [CONFIG] 立体視にしたとき HUD の縦横比がおかしい (縦につぶれる/伸びる) なら 2.0 か 0.5 を試す

# --- にじみ (発光・ぼかし) ―― くっきりしすぎを和らげ、光って見せる ----------------------------
HUD_GLOW_RADIUS_PX = 5.0                   # [CONFIG] (AC風テスト。元は 3.0) 周りににじむ光の広がり [px]。0 = なし
HUD_GLOW_STRENGTH = 0.35                   # [CONFIG] (AC風テスト。元は 0.5) にじむ光の濃さ 0.0～1.0
HUD_SOFTEN_PX = 0.3                        # [CONFIG] (AC風テスト。元は 0.6) 線そのもののぼかし [px]。0 = くっきり (0.5～1.0 がおすすめ)

# --- 操作インジゲータの細かい設定 ----------------------------------------------------
HUD_FRAME_FILES = ('input_hud_mint.png', 'input_hud.png', 'throttle_box.png')   # [CONFIG] ゲージ+ボックスの一体画像 (先に見つかったもの)
HUD_YAWLINE_FILE = 'yawline_mint.png'      # [CONFIG] (AC風テスト。元は 'yawline.png'。make_mint_png.py で作る)
HUD_CROSS_FILE = 'cross_mint.png'          # [CONFIG] (AC風テスト。元は 'cross.png')
HUD_POV_FILE = 'cross_pov_aa_mint.png'     # [CONFIG] 十字キーモードのアイコン (AC風。ほかの HUD の色に合わせたミント版。元は 'cross_pov_aa.png')
HUD_BAR_MARGIN_TOP = 4                     # [CONFIG] バーと枠線の内側とのすき間 (上) [px]
HUD_BAR_MARGIN_BOTTOM = 4                  # [CONFIG] 同 (下) [px]
HUD_BAR_MARGIN_X = 4                       # [CONFIG] 同 (左右) [px]
HUD_EDGE_INSET_PX = None                   # [CONFIG] 十字/yaw線の中心が届く位置。None = ボックス枠線の中央
HUD_POV_ICON_SIZE = None                   # [CONFIG] 十字キーアイコンの大きさ [px]。None = ゲージ上端までの空きに収まる最大
HUD_POV_ICON_FALLBACK = 48                 # [CONFIG] 自動で決められないときの大きさ [px]
HUD_POV_GAP = 4                            # [CONFIG] アイコンとボックス上端の間隔 [px]
HUD_PITCH_SIGN = -1.0                      # [CONFIG] 動きが逆なら符号を反転
HUD_ROLL_SIGN = 1.0                        # [CONFIG]
HUD_YAW_SIGN = 1.0                         # [CONFIG]
JOY_LOG_CSV = None                  # 例: 'joy_log.csv' を指定すると、出力値を60Hzで記録 (ゲーム画面との比較用)

# ==============================================================================
# [CONFIG] スロットル・アクセラレータ・リミッター (メインスロットル throttle_z 専用)
# ==============================================================================
# 前へ押していくと THROTTLE_ACCEL_LIMIT_RATIO の位置で一度止まる。そこから勢いよく押し込むと(速度が閾値以上)
# 止まらずにそのまま手の位置どおり進み、制限値以下(緑の領域)に戻るまでは自由に上下できる。超えている間はバーが黄色になる。
THROTTLE_ACCELERATOR_LIMITTER = True   # [CONFIG] リミッターを使うか
THROTTLE_ACCEL_LIMIT_RATIO = 0.8       # [CONFIG] 止める高さの割合 (約80%)
THROTTLE_ACCEL_THRESHOLD = 0.018       # [CONFIG] 100%へ突破するのに必要な押し込みの速さ (1フレームあたりの移動量[m]×感度)

# 【将来の作業用準備】クルーズモード (指定スロットルに固定し、前後させても戻すモード)
# オンの間はリミッターが干渉しない。
CRUISE_MODE_ENABLED = False            # [CONFIG]
CRUISE_MODE_Power = None               # [CONFIG] クルーズモードで固定する throttle 出力値 (未使用・予約)
# ※ スロットルの値に関わらず 50% のクルーズにする「センタークルーズ」のフラグは、仮想ボタンで代用できるかもしれない


# ==============================================================================
# HUD の文字 ― フォント読込と文字アイテム (ユーザーが編集する設定)
# ==============================================================================
# フォントはインストール不要。media/hotas_sacc/ (無ければ media/) のファイルを直接読み込む。
# ファイル名のリストにすると、先に見つかったものを使う。探す場所は media/hotas_sacc/ → media/ → Windows のフォントの場所。
# フルパスで書いてもよい。
HUD_FONT_FILES = {                         # [CONFIG]
    'hornet': 'HornetDisplay-Regular.ttf',
    'hornet_bold': 'HornetDisplay-Bold.ttf',
    'gamepad': 'gamepad_xboxone.otf',        # ボタン記号用フォント
    'jp': ['BIZ-UDGothicB.ttc', 'BIZ-UDGothicR.ttc', 'YuGothB.ttc', 'meiryob.ttc', 'meiryo.ttc', 'msgothic.ttc'],   # デバッグログの日本語用
}
HUD_TEXT_FONT = 'hornet_bold'              # [CONFIG] HUD の文字の標準フォント ('font' を書かない段・部品はこれ)。細い方は 'hornet'
HUD_TEXT_BOLDEN_PX = 0.0                   # [CONFIG] 文字をさらに太らせる幅 [px] (縁取りで太らせる)。0 = フォントのまま / 1.0～2.0 で太字よりさらに太く
                                           #          ボタン記号 (gamepad フォント) には効かない

# 仮想ボタン表記: 文字中の {btn:名前} を gamepad フォントの1文字に置き換えて描く。
# 名前 → gamepad フォント内の文字。コードは font_dump.py で作る一覧画像を見て決める。
# 例: HUD_BUTTON_GLYPHS = {'A': u'', 'B': u''}
# 未登録の名前は "[名前]" と普通の文字で描く。ゲームごとに表記を変えたいときはここを書き換える。
# gamepad_xboxone.otf の文字コード (ユーザー提供の一覧画像より)。名前は自由に足してよい。
# 十字キー/スティックの向きはキーボード配置 (QWE/ASD/ZXC, テンキー 789/456/123) になっている。
HUD_BUTTON_GLYPHS = {                      # [CONFIG]
    'A': u'\x61', 'B': u'\x62', 'X': u'\x78', 'Y': u'\x79',
    'LB': u'\x5b', 'RB': u'\x5d', 'LT': u'\x7b', 'RT': u'\x7d',
    'XBOX': u'\x67', 'MENU': u'\x6d', 'VIEW': u'\x76',
    'LS': u'\x3c', 'RS': u'\x3e',                     # スティック押し込み (L / R の印)
    # スティックの倒れ方 (テンキーの並び: 8=上, 2=下, 4=左, 6=右, 5=中立)
    'STICK': u'\x35', 'STICK_UP': u'\x38', 'STICK_DOWN': u'\x32', 'STICK_LEFT': u'\x34', 'STICK_RIGHT': u'\x36',
    'STICK_UL': u'\x37', 'STICK_UR': u'\x39', 'STICK_DL': u'\x31', 'STICK_DR': u'\x33',
    # 十字キー (キーボード配置: W=上, X=下, A=左, D=右, S=何も押していない) ※向きは画像からの推定。違えば入れ替える
    'DPAD': u'\x53', 'DPAD_UP': u'\x57', 'DPAD_DOWN': u'\x58', 'DPAD_LEFT': u'\x41', 'DPAD_RIGHT': u'\x44',
    'DPAD_UL': u'\x51', 'DPAD_UR': u'\x45', 'DPAD_DL': u'\x5a', 'DPAD_DR': u'\x43',
}

# HUD に出す文字。pos = 固まりの中心からの (右, 上) メートル、文字の中心がそこに来る。
# 例:
# HUD_TEXT_ITEMS = [
#     {'text': 'HUD', 'font': 'hornet_bold', 'size': 18, 'pos': (0.0, 0.07)},
#     {'text': 'BRAKE {btn:B}', 'font': 'hornet_bold', 'size': 14, 'pos': (0.12, 0.0),
#      'color': (206, 206, 39, 255), 'btn_scale': 1.2},
# ]
HUD_TEXT_ITEMS = []                        # [CONFIG]
HUD_TEXT_COLOR = (130, 255, 180, 255)       # [CONFIG] (AC風テスト。元は (0, 255, 42, 255))


def _text_size(font, text):
    """文字列の大きさ (描画原点(0,0)から右下まで)。Pillow の版による API の違いを吸収。"""
    if not text:
        return 0, 0
    if hasattr(font, 'getbbox'):
        l, t, r, b = font.getbbox(text)
        return int(r), int(b)
    return font.getsize(text)


class HudFonts:
    BOX_LINE = 1.0 / 14.0     # 枠線の太さ (文字の高さに対する割合)
    BOX_PAD = 0.22            # 文字と枠のすき間 (同)
    BOX_HEIGHT_RATIO = 1.0 + 2.0 * (BOX_PAD + BOX_LINE)   # 枠全体の高さ / 文字の高さ
    def __init__(self):
        this_dir = os.path.abspath(os.path.dirname(__file__))
        self._dirs = [os.path.join(this_dir, 'media', 'hotas_sacc'), os.path.join(this_dir, 'media'),
                      os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts')]
        self._cache = {}
        self.missing = set()
        self._glyph_fonts = set()    # ボタン記号のフォント (太らせない)
        self._cw = {}                # (フォント, 文字) -> 幅 [px] (ログの折り返し用)

    def _find(self, filename):
        """filename はファイル名かフルパス、またはそのリスト (先に見つかったもの)。"""
        names = filename if isinstance(filename, (list, tuple)) else [filename]
        for n in names:
            if os.path.isabs(n) and os.path.exists(n):
                return n
            for d in self._dirs:
                p = os.path.join(d, n)
                if os.path.exists(p):
                    return p
        return None

    def get(self, name, size):
        size = max(1, int(round(size)))
        key = (name, size)
        if key in self._cache:
            return self._cache[key]
        font = None
        path = self._find(HUD_FONT_FILES.get(name, name))
        if path is not None:
            try:
                font = ImageFont.truetype(path, size)
            except Exception as e:
                print("[HUD Warning] font {} could not be loaded: {}".format(path, e))
        if font is None:
            if name not in self.missing:
                print("[HUD Warning] font '{}' not found; using the default font".format(name))
            self.missing.add(name)
            font = ImageFont.load_default()
        self._cache[key] = font
        if name == 'gamepad':
            self._glyph_fonts.add(id(font))
        return font

    def _runs(self, item):
        """文字列を (文字列, フォント) の並びにする。{btn:名前} は gamepad フォントの記号。"""
        size = item.get('size', 16)
        base_font = self.get(item.get('font', HUD_TEXT_FONT), size)
        btn_font = self.get('gamepad', size * item.get('btn_scale', 1.0))
        runs = []
        for part in re.split(r'(\{btn:[^}]*\})', str(item.get('text', ''))):
            if not part:
                continue
            m = re.match(r'^\{btn:([^}]*)\}$', part)
            if m:
                glyph = HUD_BUTTON_GLYPHS.get(m.group(1))
                if glyph:
                    runs.append((glyph, btn_font))
                else:
                    runs.append(('[' + m.group(1) + ']', base_font))
            else:
                runs.append((part, base_font))
        return runs

    def render(self, item):
        """
        文字アイテム(dict)を RGBA 画像にして返す。{btn:名前} は gamepad フォントの記号にする。
        item['box'] = True なら全体を □ の枠で囲む。
        """
        color = tuple(item.get('color', HUD_TEXT_COLOR))
        runs = item['_runs'] if '_runs' in item else self._runs(item)
        if item.get('box'):
            return self._render_boxed(runs, color)
        sizes = [_text_size(f, t) for t, f in runs]
        sw = int(round(max(0.0, float(HUD_TEXT_BOLDEN_PX)) * hud_ss()))     # 太らせる幅 (内部の細かさに合わせる)
        w = max(1, sum(s[0] for s in sizes)) + 2 * sw
        h = max([s[1] for s in sizes] + [1]) + 2 * sw
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x = sw
        for (t, f), (tw, th) in zip(runs, sizes):
            pos = (x, (h - th) // 2)
            if sw > 0 and id(f) not in self._glyph_fonts:
                try:
                    d.text(pos, t, font=f, fill=color, stroke_width=sw, stroke_fill=color)   # Pillow 6.2 以降
                except TypeError:
                    for ox in range(-sw, sw + 1):                                              # 古い Pillow: ずらして重ね描き
                        for oy in range(-sw, sw + 1):
                            d.text((pos[0] + ox, pos[1] + oy), t, font=f, fill=color)
            else:
                d.text(pos, t, font=f, fill=color)
            x += tw
        bbox = img.getchannel('A').getbbox()          # 上下の空白を切る (高さをそろえやすくする)
        if bbox is not None:
            img = img.crop((0, bbox[1], w, bbox[3]))
        return img

    def _render_boxed(self, runs, color):
        """段(単語)全体を □ の枠で囲む。枠の太さと余白は文字の高さに合わせる。"""
        inner = self.render({'_runs': runs, 'color': color})
        h = inner.height
        lw = max(2, int(round(h * self.BOX_LINE)))     # 枠線の太さ
        pad = max(3, int(round(h * self.BOX_PAD)))     # 文字と枠のすき間
        w2, h2 = inner.width + 2 * (pad + lw), h + 2 * (pad + lw)
        img = Image.new('RGBA', (w2, h2), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for k in range(lw):
            d.rectangle([k, k, w2 - 1 - k, h2 - 1 - k], outline=color)
        img.alpha_composite(inner, dest=(pad + lw, pad + lw))
        return img

    # ---- デバッグログの1行 (英数字 = HUD_LOG_FONT、それ以外 = HUD_LOG_FONT_JP。高さと文字の並ぶ線をそろえる) ----
    def has_glyph(self, font, ch):
        """フォントにその文字の形があるか (Hornet は '[' ']' などが空白になる)。"""
        if ch == ' ':
            return True
        key = (id(font), ch, 'g')
        r = self._cw.get(key)
        if r is None:
            try:
                r = font.getmask(ch).getbbox() is not None
            except Exception:
                r = False
            self._cw[key] = r
        return r

    def font_for_char(self, ch, size):
        """ログの1文字に使うフォント: 英数字のフォントに形があればそれ、無ければ日本語のフォント。"""
        base = self.get(HUD_LOG_FONT, size)
        if ord(ch) < 128 and self.has_glyph(base, ch):
            return base
        return self.get(HUD_LOG_FONT_JP, size * float(HUD_LOG_JP_SCALE))

    def line_runs(self, text, size):
        """文字列を (文字列, フォント) の並びにする (font_for_char で文字ごとに選ぶ)。"""
        runs = []
        for ch in text:
            f = self.font_for_char(ch, size)
            if runs and runs[-1][1] is f:
                runs[-1][0] += ch
            else:
                runs.append([ch, f])
        return [(t, f) for t, f in runs]

    @staticmethod
    def _advance(font, text):
        if hasattr(font, 'getlength'):
            return float(font.getlength(text))
        return float(font.getsize(text)[0])

    def char_width(self, ch, size):
        f = self.font_for_char(ch, size)
        key = (id(f), ch)
        w = self._cw.get(key)
        if w is None:
            try:
                w = self._advance(f, ch)
            except Exception:
                w = float(size) * 0.6
            if len(self._cw) > 4096:
                self._cw.clear()
            self._cw[key] = w
        return w

    def wrap_line(self, text, size, width, max_lines):
        """幅 width [px] に収まるよう折り返した行のリスト。max_lines を超えたら最後の行を '...' で切る。"""
        out = []
        cur = []
        cw = 0.0
        for ch in text:
            w = self.char_width(ch, size)
            if cur and cw + w > width:
                sp = -1
                for k in range(len(cur) - 1, 0, -1):         # なるべく空白で切る
                    if cur[k] == ' ':
                        sp = k
                        break
                if sp > 0 and sp >= len(cur) // 3:
                    out.append(''.join(cur[:sp]).rstrip())
                    cur = cur[sp + 1:]
                else:
                    out.append(''.join(cur))
                    cur = []
                cw = sum(self.char_width(c, size) for c in cur)
                if len(out) > max_lines:
                    break
            cur.append(ch)
            cw += w
        if cur and len(out) <= max_lines:
            out.append(''.join(cur))
        out = out or ['']
        if len(out) > max_lines:
            out = out[:max_lines]
            last = out[-1]
            dots = '...'
            limit = width - sum(self.char_width(c, size) for c in dots)
            while last and sum(self.char_width(c, size) for c in last) > limit:
                last = last[:-1]
            out[-1] = last.rstrip() + dots
        return out

    def render_line(self, text, color, size, height):
        """1行を、高さ height [px] の画像にする (英数字と日本語の、文字の並ぶ線をそろえる)。"""
        runs = self.line_runs(text, size)
        base = self.get(HUD_LOG_FONT, size)

        def metrics(f):
            try:
                a, d = f.getmetrics()
                return int(a), int(d)
            except Exception:
                return int(size), 0
        ab, db = metrics(base)
        baseline = (height - (ab + db)) // 2 + ab
        widths = []
        for t, f in runs:
            try:
                widths.append(int(math.ceil(self._advance(f, t))))
            except Exception:
                widths.append(int(size * 0.6 * len(t)))
        img = Image.new('RGBA', (max(1, sum(widths) + 2), int(height)), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x = 0
        for (t, f), w in zip(runs, widths):
            d.text((int(x), int(baseline - metrics(f)[0])), t, font=f, fill=tuple(color))
            x += w
        return img


# ==============================================================================
# デバッグログ ― print した文字を HUD にも出す (コンソールの表示はそのまま)
#   HUD_LOG (HudLog) に行をためる。どのスレッドから足してもよい (ロック付き)。
#   HUD_LOG_CAPTURE_PRINT が True なら sys.stdout を _HudLogTee に差し替え、print を全部コンソール + HUD_LOG に送る。
#   HUD は描画スレッドで HUD_LOG.recent() を読み、操作インジゲータの上の 'log' 層に描く (HudPlateOverlay._log_key)。
# ==============================================================================
class HudLog(object):
    """デバッグログの行をためる (描画を知らない)。行 = (通し番号, 足した時刻, 文字)。表示の大きさ (mode) もここで持つ。"""
    MODES = ('normal', 'large', 'hidden')     # L キー (cycle) はこの順

    def __init__(self, maxlen=200):
        self._lock = threading.Lock()
        self._lines = deque(maxlen=maxlen)
        self.serial = 0
        m = str(HUD_LOG_START_MODE)
        self.mode = m if m in self.MODES else 'normal'     # 'normal' / 'large' / 'hidden'
        self._shown = self.mode if self.mode != 'hidden' else 'normal'   # 隠す前の表示 (toggle で戻す)

    def push(self, text):
        text = str(text).replace('\t', '    ').rstrip()
        if HUD_LOG_SHORTEN:
            text = _hud_log_shorten(text)
        if not text.strip():
            return
        with self._lock:
            self.serial += 1
            self._lines.append((self.serial, time.time(), text))

    def recent(self, now, count, hold_sec):
        """新しい方から最大 count 個 (古い順に並べて返す)。hold_sec を過ぎたものは出さない (0/None = ずっと)。"""
        out = []
        with self._lock:
            for serial, t, text in reversed(self._lines):
                if len(out) >= count:
                    break
                if hold_sec and now - t > hold_sec:
                    break
                out.append((serial, text))
        out.reverse()
        return out

    def clear(self):
        with self._lock:
            self._lines.clear()

    @property
    def visible(self):
        return self.mode != 'hidden'

    @visible.setter
    def visible(self, on):
        if on:
            self.mode = self._shown
        elif self.mode != 'hidden':
            self._shown = self.mode
            self.mode = 'hidden'

    def toggle(self):
        """隠す / 出す (出すときは隠す前の大きさ)。"""
        self.visible = not self.visible
        return self.visible

    def cycle(self):
        """普通 → 大きく → 隠す → 普通。新しい mode を返す。"""
        self.mode = self.MODES[(self.MODES.index(self.mode) + 1) % len(self.MODES)]
        if self.mode != 'hidden':
            self._shown = self.mode
        return self.mode


def _hud_log_shorten(text):
    """HUD 用に短くする (0.1.13): 括弧 () （） の中を省き、続く空白を1つにする。行頭の [HUD] などの見出しは残る。"""
    out = []
    depth = 0
    for ch in text:
        if ch in '(（':
            depth += 1
            continue
        if ch in ')）' and depth > 0:
            depth -= 1
            continue
        if depth == 0:
            out.append(ch)
    r = ' '.join(''.join(out).split())
    return r if r else text


HUD_LOG = HudLog()


class _HudLogTee(object):
    """sys.stdout / sys.stderr の代わり。元の出力 (コンソール) に書き、1行ごとに HUD_LOG にも足す。"""

    def __init__(self, stream, log):
        self._stream = stream
        self._log = log
        self._buf = ''
        self._buf_lock = threading.Lock()

    def write(self, s):
        n = len(s)
        if self._stream is not None:
            r = self._stream.write(s)
            n = r if r is not None else n
        try:
            with self._buf_lock:
                self._buf += s
                lines = self._buf.split('\n')
                self._buf = lines.pop()
            for line in lines:
                self._log.push(line.split('\r')[-1])        # '\r' で書き直す行は最後の部分だけ
        except Exception:
            pass
        return n

    def flush(self):
        if self._stream is not None:
            self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def hud_log_install():
    """print を HUD にも送るようにする (HUD_LOG_CAPTURE_PRINT / HUD_LOG_CAPTURE_STDERR)。何度呼んでも1回だけ。"""
    import sys
    if not HUD_LOG_ENABLED:
        return
    if HUD_LOG_CAPTURE_PRINT and not isinstance(sys.stdout, _HudLogTee):
        sys.stdout = _HudLogTee(sys.stdout, HUD_LOG)
    if HUD_LOG_CAPTURE_STDERR and not isinstance(sys.stderr, _HudLogTee):
        sys.stderr = _HudLogTee(sys.stderr, HUD_LOG)


def hud_log(*args):
    """コンソールと HUD の両方に出す (print と同じ書き方)。print を HUD に送っていないときも HUD に出る。"""
    import sys
    text = ' '.join(str(a) for a in args)
    if isinstance(sys.stdout, _HudLogTee):
        print(text)
    else:
        print(text)
        HUD_LOG.push(text)


hud_log_install()


# ==============================================================================
# HUD 1枚板方式 ― 構成
#   HudAssets       素材(画像・フォント)の読込
#   HudLayout       2Dレイアウト専用。部品の大きさと位置[px]だけを決める (奥行きもOpenVRも知らない)
#   HudDepth        奥行き(視差)専用。HUD全体で1つの距離と頭の位置から「オーバーレイを置く位置と幅」だけを返す (画像は触らない)
#   HudNoticeBoard  システム通知インジゲータ専用。段の構造・仮想ボタン番号のトリガー・色ルール (描画を知らない)
#   HudPlateOverlay 上の4つを使って1枚の動的テクスチャに描き、SteamVRへ送る (GL/OpenVRはここだけ)
# 設定は上の [CONFIG] ブロック。Python 3.5 で動く書き方 (f文字列などを使わない) にしてある。
# ==============================================================================
class _Bag(object):
    """属性を自由に持たせるだけの入れ物"""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _hud_media_dirs():
    this_dir = os.path.abspath(os.path.dirname(__file__))
    return [os.path.join(this_dir, 'media', 'hotas_sacc'), os.path.join(this_dir, 'media')]


def hud_load_image(filename, crop=True, quiet=False):
    """media/hotas_sacc/ → media/ の順に探して読む。crop=True は透明な余白を切り詰める。"""
    for d in _hud_media_dirs():
        path = os.path.join(d, filename)
        if os.path.exists(path):
            try:
                img = Image.open(path).convert('RGBA')
                if crop:
                    bbox = img.getchannel('A').getbbox()
                    if bbox is not None:
                        img = img.crop(bbox)
                return img
            except Exception as e:
                print("[HUD Warning] Failed to load {}: {}".format(filename, e))
                return None
    if not quiet:
        print("[HUD Warning] {} not found".format(filename))
    return None


def _hud_scaled(img, mult):
    if img is None or abs(mult - 1.0) < 1e-6:
        return img
    w = max(1, int(round(img.width * mult)))
    h = max(1, int(round(img.height * mult)))
    return img.resize((w, h), Image.LANCZOS)


def _hud_main_color(img):
    """画像の見えている部分の平均色 (にじみの色に使う)。"""
    from PIL import ImageStat
    a = img.getchannel('A')
    if a.getbbox() is None:
        return (0, 255, 42)
    st = ImageStat.Stat(img.convert('RGB'), mask=a.point(lambda v: 255 if v > 64 else 0))
    if not st.count or st.count[0] == 0:
        return (0, 255, 42)
    return tuple(int(round(v)) for v in st.mean[:3])


def hud_ss():
    """内部の絵の細かさの倍率 (HUD_RENDER_SCALE)。px で書いた設定はこれを掛けて使う。"""
    return max(0.5, min(4.0, float(HUD_RENDER_SCALE)))


def hud_glow_pad():
    """にじみで絵が広がる幅 [px]。"""
    r = max(0.0, float(HUD_GLOW_RADIUS_PX)) * hud_ss()
    s = max(0.0, float(HUD_SOFTEN_PX)) * hud_ss()
    if r <= 0.0 and s <= 0.0:
        return 0
    return int(math.ceil(2.5 * max(r, s))) + 1


def hud_glow(img, opacity=None):
    """
    にじみを付けた絵を返す (上下左右に hud_glow_pad() だけ大きくなる)。
      ・HUD_SOFTEN_PX    : 線そのものの輪郭を少しぼかす
      ・HUD_GLOW_RADIUS_PX / HUD_GLOW_STRENGTH : 同じ色の光を周りににじませる (下に敷く)
    """
    from PIL import ImageFilter
    pad = hud_glow_pad()
    if img is None:
        return img
    if pad == 0:
        return hud_fade(img, opacity)
    color = _hud_main_color(img)
    w, h = img.width + 2 * pad, img.height + 2 * pad
    a = Image.new('L', (w, h), 0)
    a.paste(img.getchannel('A'), (pad, pad))
    # 透明部分の色を主な色で埋めておく (ぼかしたときに縁が黒ずまないように)
    rgb = Image.new('RGB', (w, h), color)
    rgb.paste(img.convert('RGB'), (pad, pad), img.getchannel('A').point(lambda v: 255 if v > 0 else 0))
    soft = max(0.0, float(HUD_SOFTEN_PX)) * hud_ss()
    if soft > 0.0:
        a = a.filter(ImageFilter.GaussianBlur(soft))
    body = rgb.convert('RGBA')
    body.putalpha(a)
    radius = max(0.0, float(HUD_GLOW_RADIUS_PX)) * hud_ss()
    strength = _hud_clamp(HUD_GLOW_STRENGTH, 0.0, 1.0)
    if radius <= 0.0 or strength <= 0.0:
        return hud_fade(body, opacity)
    ga = a.filter(ImageFilter.GaussianBlur(radius)).point(lambda v: int(min(255, v * strength * 1.6)))
    out = Image.new('RGBA', (w, h), tuple(color) + (0,))
    out.putalpha(ga)
    out.alpha_composite(body)
    return hud_fade(out, opacity)


def hud_fade(img, opacity=None):
    """HUD_OPACITY (opacity を渡せばその値) だけ透かす (線・文字・記号用。薄板や縦線には使わない)。"""
    op = _hud_clamp(HUD_OPACITY if opacity is None else opacity, 0.0, 1.0)
    if img is None or op >= 0.999:
        return img
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    out = img.copy()
    out.putalpha(img.getchannel('A').point(lambda v: int(v * op + 0.5)))
    return out


def hud_fade_by(img, a):
    """絵全体を a (0～1) 倍の濃さにする (起動時の表示を消すとき)。"""
    out = img.copy()
    out.putalpha(img.getchannel('A').point(lambda v: int(v * a + 0.5)))
    return out


def _hud_recolor(img, rgb):
    """画像の形(アルファ)はそのままで、色だけ rgb に塗り替える。"""
    solid = Image.new('RGBA', img.size, tuple(rgb[:3]) + (255,))
    solid.putalpha(img.getchannel('A'))
    return solid


def _hud_blit(canvas, img, pos):
    """アルファ合成。キャンバスの外へはみ出してもクリップする。"""
    x, y = int(pos[0]), int(pos[1])
    cw, ch = canvas.size
    sx0 = max(0, -x)
    sy0 = max(0, -y)
    sx1 = min(img.width, cw - x)
    sy1 = min(img.height, ch - y)
    if sx1 <= sx0 or sy1 <= sy0:
        return
    canvas.alpha_composite(img.crop((sx0, sy0, sx1, sy1)), dest=(x + sx0, y + sy0))


def _hud_knockout_lut(top):
    """
    絵の不透明度 a → 下の薄板を抜く割合 (0～255)。top = その絵の線の本体の不透明度 (いちばん濃いところ)。
    本体 (a が top の 9 割以上) は全部抜き、薄いにじみ (top の 45% 以下) は抜かない。間はなめらかに。
    """
    top = max(1, int(top))
    lo, hi = 0.45 * top, 0.9 * top
    return [0 if v <= lo else (255 if v >= hi else int(255 * (v - lo) / (hi - lo))) for v in range(256)]


def _hud_blit_ko(canvas, img, pos):
    """
    _hud_blit と同じだが、先に canvas (下の薄板) の、img の線・文字の形の所だけ透明にする (HUD_PANEL_KNOCKOUT)。
    薄板の灰色と線の色が混ざらず、線は景色の上に直接重なる。薄板が無い所には何も起きない。
    """
    if HUD_PANEL_KNOCKOUT and img is not None:
        from PIL import ImageChops
        x, y = int(pos[0]), int(pos[1])
        cw, ch = canvas.size
        sx0, sy0 = max(0, -x), max(0, -y)
        sx1, sy1 = min(img.width, cw - x), min(img.height, ch - y)
        if sx1 > sx0 and sy1 > sy0:
            a = img.getchannel('A').crop((sx0, sy0, sx1, sy1))
            top = a.getextrema()[1]
            if top > 0:
                k = a.point(_hud_knockout_lut(top))
                box = (x + sx0, y + sy0, x + sx1, y + sy1)
                region = canvas.crop(box)
                region.putalpha(ImageChops.multiply(region.getchannel('A'), ImageChops.invert(k)))
                canvas.paste(region, box)
    _hud_blit(canvas, img, pos)


def _hud_clamp(v, lo, hi):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return 0.0
    if v != v or v in (float('inf'), float('-inf')):
        return 0.0
    return max(lo, min(hi, v))


def _hud_split_frame(frame):
    """ゲージ+ボックス一体画像から、ゲージ(左)とボックス(右)の矩形 (l,t,r,b) と枠線の太さを求める。"""
    a = frame.getchannel('A')
    filled = [a.crop((x, 0, x + 1, frame.height)).getbbox() is not None for x in range(frame.width)]
    runs = []
    start = None
    for x, on in enumerate(filled + [False]):
        if on and start is None:
            start = x
        elif not on and start is not None:
            runs.append((start, x))
            start = None
    if len(runs) < 2:
        cut = max(1, int(frame.width * 0.17))
        runs = [(0, cut), (cut, frame.width)]
    rects = []
    for x0, x1 in (runs[0], runs[-1]):
        l, t, r, b = a.crop((x0, 0, x1, frame.height)).getbbox() or (0, 0, x1 - x0, frame.height)
        rects.append((x0 + l, t, x0 + r, b))

    def border(rect):
        l, t, r, b = rect
        y = t + (b - t) // 4      # 中央の十字仕切りを避ける
        n = 0
        for x in range(l, r):
            if a.getpixel((x, y)) > 0:
                n += 1
            else:
                break
        return max(1, n)

    return rects[0], rects[1], border(rects[0]), border(rects[1])


_HUD_PART_KEYS = ('image', 'text', 'text_fn', 'reserve', 'align', 'box', 'font', 'size', 'btn_scale', 'recolor')


def hud_normalize_notice_rows(rows):
    """HUD_NOTICE_ROWS の各段に既定値を補い、中身を 'parts' (部品のリスト) の形にそろえる。"""
    out = []
    for i, r in enumerate(rows):
        row = dict(r)
        row.setdefault('id', 'row{}'.format(i))
        row['on'] = list(row.get('on', []))
        row['hold_sec'] = max(0.0, float(row.get('hold_sec', 0.0)))
        row['color'] = tuple(row.get('color', HUD_COLOR_GREEN))
        rules = []
        for rule in row.get('color_rules', []):
            rules.append({'when': list(rule.get('when', [])), 'color': tuple(rule['color'])})
        row['color_rules'] = rules
        row['panel'] = bool(row.get('panel', True))
        if 'parts' in row:
            parts = [dict(pt) for pt in row['parts']]
        else:
            parts = [dict((k, row[k]) for k in _HUD_PART_KEYS if k in row)]
        for pt in parts:
            pt['box'] = bool(pt.get('box', False))
            pt['recolor'] = bool(pt.get('recolor', False))
            pt.setdefault('font', HUD_TEXT_FONT)
            pt.setdefault('align', 'right')
            if not pt.get('image') and not pt.get('text_fn') and not pt.get('text'):
                pt['text'] = '[{}]'.format(row['id'])
        row['parts'] = parts
        # 色が見た目に効くのは「文字」か「recolor する画像」だけ
        row['uses_color'] = any((not pt.get('image')) or pt['recolor'] for pt in parts)
        # 毎回文字を作る部品があるか (あれば、その文字が変わったときだけ描き直す)
        row['dynamic'] = any(callable(pt.get('text_fn')) for pt in parts)
        out.append(row)
    return out


def hud_row_texts(row, values):
    """'text_fn' を持つ部品の文字を作る (その他の部品は None)。関数が失敗したら '?'。"""
    texts = []
    for pt in row['parts']:
        fn = pt.get('text_fn')
        if callable(fn):
            try:
                texts.append(str(fn(values)))
            except Exception:
                texts.append('?')
        else:
            texts.append(None)
    return tuple(texts)


class HudAssets(object):
    """素材の読込。画像は起動時に1回だけ読む。"""

    def __init__(self):
        green = HUD_COLOR_GREEN
        self.fonts = HudFonts()
        self._raw = {}
        self._row_cache = {}
        self._part_cache = {}     # 部品ごとの文字の大きさ・確保する幅

        self.frame = None
        for fname in HUD_FRAME_FILES:
            self.frame = hud_load_image(fname, quiet=True)
            if self.frame is not None:
                break
        if self.frame is None:
            self.frame = self._fallback_frame()
        self.yawline = hud_load_image(HUD_YAWLINE_FILE)
        if self.yawline is None:
            self.yawline = Image.new('RGBA', (5, 152), green)
        self.cross = hud_load_image(HUD_CROSS_FILE)
        if self.cross is None:
            self.cross = Image.new('RGBA', (20, 20), (0, 0, 0, 0))
            d = ImageDraw.Draw(self.cross)
            d.line([(0, 0), (19, 19)], fill=green, width=2)
            d.line([(0, 19), (19, 0)], fill=green, width=2)
        self.pov = hud_load_image(HUD_POV_FILE)

        self.bar_color = HUD_BAR_COLOR_NORMAL
        if self.bar_color is None:
            px = None
            pixel = hud_load_image('throttlebar_pixel.png', quiet=True)
            if pixel is not None:
                px = pixel.getpixel((pixel.width // 2, pixel.height // 2))
            if px is None or px[3] == 0:
                px = self.frame.getpixel((0, self.frame.height // 2))
            self.bar_color = (px[0], px[1], px[2]) if px[3] > 0 else (0, 255, 42)

    def _fallback_frame(self):
        green = (0, 255, 0, 255)
        g = Image.new('RGBA', (30, 221), (0, 0, 0, 0))
        ImageDraw.Draw(g).rectangle([0, 0, 29, 220], outline=green, width=4)
        b = Image.new('RGBA', (152, 152), (0, 0, 0, 0))
        d = ImageDraw.Draw(b)
        d.rectangle([0, 0, 151, 151], outline=green, width=4)
        d.line([(75, 0), (75, 151)], fill=green, width=4)
        d.line([(0, 75), (151, 75)], fill=green, width=4)
        f = Image.new('RGBA', (30 + 24 + 152, 221), (0, 0, 0, 0))
        f.alpha_composite(g, dest=(0, 0))
        f.alpha_composite(b, dest=(54, 221 - 152))
        return f

    def raw_image(self, name):
        if name not in self._raw:
            self._raw[name] = hud_load_image(name)
        return self._raw[name]

    def row_art(self, row, color, mult, texts=None):
        """
        通知の段1つ分の絵を color で作る。部品 ('parts') を左から並べ、高さの真ん中をそろえる。
        texts = 'text_fn' の部品に入れる文字 (hud_row_texts の結果)。None なら 'reserve' の文字で作る (レイアウト用)。
        同じ組み合わせは使い回す。
        """
        key = (row['id'], tuple(color) if color else None, mult, texts)
        img = self._row_cache.get(key)
        if img is not None:
            return img
        c = tuple(color) if color else tuple(row['color'])
        height = max(4, int(round(row.get('height', HUD_NOTICE_ROW_HEIGHT_PX) * mult)))   # 段の高さ [px]
        arts = []
        for i, pt in enumerate(row['parts']):
            text = texts[i] if (texts is not None and texts[i] is not None) else None
            arts.append(self._part_art(row, i, pt, c, height, mult, text))
        gap = int(round(HUD_NOTICE_PART_GAP_PX * mult)) if len(arts) > 1 else 0
        w = sum(a.width for a in arts) + gap * (len(arts) - 1)
        h = max(a.height for a in arts)
        img = Image.new('RGBA', (max(1, w), max(1, h)), (0, 0, 0, 0))
        x = 0
        for a in arts:
            img.alpha_composite(a, dest=(x, (h - a.height) // 2))
            x += a.width + gap
        img = hud_glow(img)
        if len(self._row_cache) > 512:
            self._row_cache.clear()
        self._row_cache[key] = img
        return img

    def _part_art(self, row, i, pt, c, height, mult, text):
        """段の中の部品1つ (にじみ前)。"""
        if pt.get('image'):
            raw = self.raw_image(pt['image'])
            if raw is not None:
                img = raw.resize((max(1, int(round(raw.width * height / float(raw.height)))), height), Image.LANCZOS)
                return _hud_recolor(img, c) if pt['recolor'] else img
            text = '[{}]'.format(pt['image'])
        if text is None:
            text = pt.get('text') or pt.get('reserve') or ''
        item = {'text': text, 'font': pt['font'], 'color': c,
                'btn_scale': pt.get('btn_scale', 1.0), 'box': pt['box'],
                'size': self._part_size(row, i, pt, height, mult)}
        img = self.fonts.render(item)
        reserve = pt.get('reserve')
        if reserve:
            # 'reserve' の文字が入る幅を確保し、その中で寄せる (数字が変わっても段の幅が変わらない)
            rkey = (row['id'], i, mult, 'w')
            rw = self._part_cache.get(rkey)
            if rw is None:
                rw = self.fonts.render(dict(item, text=reserve)).width
                self._part_cache[rkey] = rw
            if img.width < rw:
                canvas = Image.new('RGBA', (rw, img.height), (0, 0, 0, 0))
                al = pt.get('align', 'right')
                x = rw - img.width if al == 'right' else ((rw - img.width) // 2 if al == 'center' else 0)
                canvas.alpha_composite(img, dest=(x, 0))
                img = canvas
        return img

    def _part_size(self, row, i, pt, height, mult):
        """
        文字の大きさ (フォントの size)。部品ごとに1回だけ決めて覚える (値が変わっても大きさは変わらない)。
        枠付きは「枠の外側」、枠なしは「文字」を目標の高さにする (枠なしの文字は、枠付きの中の文字と同じ大きさ)。
        """
        if 'size' in pt:
            return pt['size'] * mult
        skey = (row['id'], i, mult, 's')
        size = self._part_cache.get(skey)
        if size is not None:
            return size
        target = height if pt['box'] else max(4, int(round(height / HudFonts.BOX_HEIGHT_RATIO)))
        probe = {'text': pt.get('reserve') or pt.get('text') or 'H0', 'font': pt['font'], 'color': (255, 255, 255, 255),
                 'btn_scale': pt.get('btn_scale', 1.0), 'box': pt['box'], 'size': float(height)}
        for _ in range(2):          # 2回補正すればほぼぴったり
            h = self.fonts.render(probe).height
            if h <= 0 or abs(h - target) <= 1:
                break
            probe['size'] = max(4.0, probe['size'] * target / float(h))
        self._part_cache[skey] = probe['size']
        return probe['size']


class HudLayout(object):
    """
    2Dレイアウト専用。部品の「大きさ」と「位置」をピクセルで決めるだけで、奥行き(視差)も OpenVR も知らない。
    座標はすべて 基準点(HUD_PLATE_POS) を原点とした px (右+, 下+)。板(窓)の左上を原点にした位置が base。
    """

    def __init__(self, assets, rows, mpp, size_mult=None, extra_margin_x=0):
        self.assets = assets
        self.rows = rows
        self.extra_margin_x = max(0, int(extra_margin_x))   # 立体視で左右の目の絵がずれる分 (窓を横に広げる)
        self.mult = size_mult or {}        # 部品ごとの大きさの倍率 (内部用。既定はすべて 1.0)
        self.mpp = float(mpp)
        self.panel_on = bool(HUD_PANEL_ENABLED)
        self.ss = hud_ss()
        self.panel_m = max(0, int(round(HUD_PANEL_MARGIN_PX * self.ss))) if self.panel_on else 0
        a = int(round(255 * _hud_clamp(HUD_PANEL_ALPHA, 0.0, 1.0)))
        self.panel_rgba = tuple(HUD_PANEL_COLOR[:3]) + (a,)
        self._build_indicator()
        self._build_texts()
        self._build_rows()
        self._build_version()
        self._build_log()
        self.splash = None
        self._build_window()          # 起動時の表示の位置 (自動) は、ほかの部品で決まる窓から決める
        self._build_splash()
        self._build_window()

    # ---- 操作インジゲータ ----
    def _build_indicator(self):
        mult = self.mult.get('indicator', 1.0)
        a = self.assets
        frame = _hud_scaled(a.frame, mult)
        gauge, box, g_bd, b_bd = _hud_split_frame(frame)
        fw, fh = frame.size
        rects = [(0, 0, fw, fh)]
        gap = max(1, int(round(HUD_POV_GAP * mult)))
        pov = None
        pov_xy = None
        if a.pov is not None:
            if HUD_POV_ICON_SIZE is not None:
                size = int(round(HUD_POV_ICON_SIZE * mult))
            else:
                avail = box[1] - gauge[1] - gap          # ゲージ上端～ボックス上端の空き
                size = min(avail, box[2] - box[0]) if avail >= 8 else int(round(HUD_POV_ICON_FALLBACK * mult))
            size = max(1, size)
            pov = a.pov.resize((size, max(1, int(round(a.pov.height * size / float(a.pov.width))))),
                               Image.LANCZOS)
            pov_xy = (box[0], box[1] - gap - pov.height)
            rects.append((pov_xy[0], pov_xy[1], pov_xy[0] + pov.width, pov_xy[1] + pov.height))
        minx = min(r[0] for r in rects)
        miny = min(r[1] for r in rects)
        maxx = max(r[2] for r in rects)
        maxy = max(r[3] for r in rects)
        bw, bh = maxx - minx, maxy - miny

        yaw = _hud_scaled(a.yawline, mult)
        cross = _hud_scaled(a.cross, mult)
        m = max(self.panel_m, int(round(HUD_INDICATOR_PANEL_PAD_PX * mult))) if self.panel_on else 0
        gp = hud_glow_pad()
        pad = max(m, (cross.width + 1) // 2, (cross.height + 1) // 2, (yaw.width + 1) // 2) + 1 + gp
        ox, oy = pad - minx, pad - miny              # 一体画像の座標 → 層の内側の座標

        def sc(v):
            return max(0, int(round(v * mult)))

        gl, gt, gr, gb = gauge[0] + ox, gauge[1] + oy, gauge[2] + ox, gauge[3] + oy
        bar_x0 = gl + g_bd + sc(HUD_BAR_MARGIN_X)
        bar_x1 = gr - g_bd - sc(HUD_BAR_MARGIN_X)
        bar_y0 = gt + g_bd + sc(HUD_BAR_MARGIN_TOP)
        bar_y1 = gb - g_bd - sc(HUD_BAR_MARGIN_BOTTOM)
        if bar_x1 <= bar_x0:
            bar_x1 = bar_x0 + 1
        if bar_y1 <= bar_y0:
            bar_y1 = bar_y0 + 1

        inset = (b_bd / 2.0) if HUD_EDGE_INSET_PX is None else float(HUD_EDGE_INSET_PX) * mult
        bl, bt, br, bb = box[0] + ox, box[1] + oy, box[2] + ox, box[3] + oy

        g = _Bag()
        g.frame, g.pov, g.yaw, g.cross = frame, pov, yaw, cross
        # にじみ付きの絵 (位置は元の絵の左上から glow_pad だけ左上へずらして描く)
        g.glow_pad = gp
        g.frame_g = hud_glow(frame)
        g.pov_g = hud_glow(pov) if pov is not None else None
        g.yaw_g = hud_glow(yaw)
        g.cross_g = hud_glow(cross)
        g.frame_xy = (ox, oy)
        g.pov_xy = (pov_xy[0] + ox, pov_xy[1] + oy) if pov is not None else None
        g.size = (bw + 2 * pad, bh + 2 * pad)
        g.content_pad = pad          # 層の左上から、部品 (一体画像とアイコン) の左上まで [px]
        g.panel_m = m                # 薄板が部品からはみ出す幅 [px]
        if self.panel_on:
            g.panel_img = Image.new('RGBA', (bw + 2 * m, bh + 2 * m), self.panel_rgba)
            g.panel_xy = (pad - m, pad - m)
        else:
            g.panel_img = None
            g.panel_xy = (0, 0)
        g.bar_x0, g.bar_x1, g.bar_y0, g.bar_y1 = bar_x0, bar_x1, bar_y0, bar_y1
        g.bar_w = bar_x1 - bar_x0
        g.bar_inner_h = bar_y1 - bar_y0
        g.box_cx, g.box_cy = (bl + br) / 2.0, (bt + bb) / 2.0
        g.travel_x = max(0.0, (br - bl) / 2.0 - inset)
        g.travel_y = max(0.0, (bb - bt) / 2.0 - inset)
        g.center = (HUD_INDICATOR_OFFSET[0] / self.mpp, -HUD_INDICATOR_OFFSET[1] / self.mpp)
        g.topleft = (int(round(g.center[0] - g.size[0] / 2.0)), int(round(g.center[1] - g.size[1] / 2.0)))
        self.ind = g

    # ---- 文字 (HUD_TEXT_ITEMS) ----
    def _build_texts(self):
        self.texts = []
        mult = self.mult.get('text', 1.0)
        for item in HUD_TEXT_ITEMS:
            try:
                it = dict(item)
                it['size'] = it.get('size', 16) * mult
                art = hud_glow(self.assets.fonts.render(it))
            except Exception as e:
                print("[HUD Warning] text item skipped ({}): {}".format(item, e))
                continue
            panel = self.panel_on and bool(item.get('panel', False))
            m = self.panel_m if panel else 0
            img = Image.new('RGBA', (art.width + 2 * m, art.height + 2 * m), (0, 0, 0, 0))
            if panel:
                img.alpha_composite(Image.new('RGBA', img.size, self.panel_rgba))
            _hud_blit_ko(img, art, (m, m))
            dx, dy = item.get('pos', (0.0, 0.0))
            cx = self.ind.center[0] + dx / self.mpp
            cy = self.ind.center[1] - dy / self.mpp
            self.texts.append(_Bag(img=img, size=img.size,
                                   topleft=(int(round(cx - img.width / 2.0)), int(round(cy - img.height / 2.0)))))

    # ---- 通知の段 ----
    def _build_rows(self):
        self.row_geo = []
        mult = self.mult.get('notice', 1.0)
        sizes = []
        for row in self.rows:
            art = self.assets.row_art(row, row['color'], mult)
            m = self.panel_m if (self.panel_on and row['panel']) else 0
            sizes.append((art.width + 2 * m, art.height + 2 * m, m))
        colw = max([s[0] for s in sizes] or [0])
        ax = HUD_NOTICE_OFFSET[0] / self.mpp
        ay = -HUD_NOTICE_OFFSET[1] / self.mpp
        self.notice_col = (ax, colw)        # 通知の列の中心 x と幅 (バージョン表記の位置合わせに使う)
        prev_cy = None
        prev_h = 0
        prev_space = 0.0
        for i, (w, h, m) in enumerate(sizes):
            cy = ay if i == 0 else prev_cy + prev_h / 2.0 + HUD_NOTICE_ROW_GAP_PX * self.ss + prev_space + h / 2.0
            if HUD_NOTICE_ALIGN == 'left':
                cx = ax - colw / 2.0 + w / 2.0
            elif HUD_NOTICE_ALIGN == 'right':
                cx = ax + colw / 2.0 - w / 2.0
            else:
                cx = ax
            self.row_geo.append(_Bag(size=(w, h), margin=m,
                                     topleft=(int(round(cx - w / 2.0)), int(round(cy - h / 2.0)))))
            prev_cy, prev_h = cy, h
            prev_space = float(self.rows[i].get('space_after_px', 0)) * mult

    def _static_text(self, text, size, color, panel, opacity=None):
        """にじみ + (必要なら) 薄板付きの文字の絵。"""
        art = hud_glow(self.assets.fonts.render({'text': text, 'font': HUD_TEXT_FONT, 'size': size, 'color': color}),
                       opacity)
        m = self.panel_m if (self.panel_on and panel) else 0
        img = Image.new('RGBA', (art.width + 2 * m, art.height + 2 * m), (0, 0, 0, 0))
        if m:
            img.alpha_composite(Image.new('RGBA', img.size, self.panel_rgba))
        _hud_blit_ko(img, art, (m, m))
        return img, m

    # ---- バージョン表記 (通知の段の数段上 = 右上の端) ----
    def _build_version(self):
        self.version = None
        if not HUD_VERSION_SHOW:
            return
        mult = self.mult.get('notice', 1.0)
        img, m = self._static_text(app_version_short(), float(HUD_VERSION_FONT_PX) * mult,
                                   tuple(HUD_VERSION_COLOR), HUD_VERSION_PANEL)
        ax, colw = self.notice_col
        top0 = self.row_geo[0].topleft[1] if self.row_geo else int(round(-HUD_NOTICE_OFFSET[1] / self.mpp))
        step = (HUD_NOTICE_ROW_HEIGHT_PX + HUD_NOTICE_ROW_GAP_PX) * mult
        bottom = top0 - float(HUD_VERSION_ROWS_ABOVE) * step
        w = img.width
        gp = hud_glow_pad()
        if HUD_VERSION_ALIGN == 'right':
            # HUD の右端 (いちばん右まで出ている部品の右端。窓の余白 HUD_PLATE_MARGIN_PX の内側) に右揃え
            rights = [g.topleft[0] + g.size[0] for g in [self.ind] + self.texts + self.row_geo]
            x = max(rights) - w
        elif HUD_NOTICE_ALIGN == 'left':
            x = ax - colw / 2.0 - gp          # 文字の左端を通知の列の左端 (段の薄板の左端) にそろえる
        elif HUD_NOTICE_ALIGN == 'right':
            x = ax + colw / 2.0 - w + gp
        else:
            x = ax - w / 2.0
        self.version = _Bag(img=img, size=img.size, topleft=(int(round(x)), int(round(bottom - img.height))))

    # ---- 起動時の表示 (中央に大きくシステム名とバージョン) ----
    def _build_splash(self):
        self.splash = None
        if not HUD_SPLASH_SEC or float(HUD_SPLASH_SEC) <= 0:
            return
        mult = self.mult.get('notice', 1.0)
        c = tuple(HUD_SPLASH_COLOR)
        op = HUD_SPLASH_OPACITY
        title, _ = self._static_text(APP_NAME, float(HUD_SPLASH_TITLE_PX) * mult, c, False, op)
        sub, _ = self._static_text('VERSION {}   (BASE: STEAM-VR-WHEEL {})'.format(APP_VERSION, APP_BASE_VERSION),
                                   float(HUD_SPLASH_SUB_PX) * mult, c, False, op)
        gap = int(round(HUD_SPLASH_SUB_PX * 0.6 * mult))
        pa = _hud_clamp(HUD_SPLASH_PANEL_ALPHA, 0.0, 1.0)
        m = int(round(HUD_SPLASH_SUB_PX * 0.8 * mult)) if pa > 0 else 0       # 文字の周りの板の余白
        w = max(title.width, sub.width) + 2 * m
        h = title.height + gap + sub.height + 2 * m
        img = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        if pa > 0:
            # 後ろの HUD の部品 (この層の下に描かれる) や明るい景色を隠す濃い板
            img.alpha_composite(Image.new('RGBA', img.size, tuple(HUD_PANEL_COLOR[:3]) + (int(round(255 * pa)),)))
        _hud_blit_ko(img, title, ((w - title.width) // 2, m))
        _hud_blit_ko(img, sub, ((w - sub.width) // 2, m + title.height + gap))
        if HUD_SPLASH_OFFSET is not None:
            cx = HUD_SPLASH_OFFSET[0] / self.mpp
            cy = -HUD_SPLASH_OFFSET[1] / self.mpp
        else:
            # 自動: 左右は窓の真ん中、上下はバージョン表記の下端～通知の1段目の上端の真ん中 (他の部品と重ならない空き)
            wl, wt, wr, wb = self.window
            cx = (wl + wr) / 2.0
            top = (self.version.topleft[1] + self.version.size[1]) if self.version is not None else wt
            low = min(r.topleft[1] for r in self.row_geo) if self.row_geo else 0
            cy = (top + low) / 2.0 if low - top >= h else (wt + wb) / 2.0
        self.splash = _Bag(img=img, size=img.size, topleft=(int(round(cx - w / 2.0)), int(round(cy - h / 2.0))))

    # ---- デバッグログ (操作インジゲータの上、左揃え) ----
    def _build_log(self):
        """
        ログの場所を取る。普通 (self.log) と大きく (self.log_large) の2つ。どちらも同じ場所に重ねて取り、片方だけ出す。
        行数ぶんの高さを最初から確保し (行が増えても板の大きさは変わらない)、
        文字の左端を操作インジゲータの部品の左端 (ゲージの枠線) にそろえ、下端をインジゲータの薄板の上に置く。
        HUD_LOG_LINES = None なら、上端がバージョン表記 (右上の端) の高さを越えない行数にする (大きくは行数が減る)。
        幅は HUD_LOG_WIDTH_PX (None = 通知の列の手前まで)。
        """
        self.log = None
        self.log_large = None
        self.logs = []
        if not HUD_LOG_ENABLED:
            return
        mult = self.mult.get('log', 1.0)
        ind = self.ind
        left = ind.topleft[0] + ind.content_pad
        ind_top = ind.topleft[1] + ind.content_pad - ind.panel_m      # インジゲータの薄板の上端
        panel_m = max(self.panel_m, int(round(4 * mult))) if (self.panel_on and HUD_LOG_PANEL) else 0
        glow_pad = hud_glow_pad() if HUD_LOG_GLOW else 0
        p = panel_m + glow_pad + 1
        gap = int(round(float(HUD_LOG_GAP_PX) * mult))
        bottom = ind_top - gap - panel_m
        # 自動の幅: 通知の列 (段の薄板) の左端の手前まで
        if self.row_geo:
            notice_left = min(r.topleft[0] for r in self.row_geo)
        else:
            notice_left = int(round((HUD_NOTICE_OFFSET[0]) / self.mpp))
        auto_w = notice_left - gap * 2 - panel_m - left
        if HUD_LOG_WIDTH_PX is None:
            text_w = auto_w
        else:
            text_w = int(round(float(HUD_LOG_WIDTH_PX) * mult))
        text_w = max(64, text_w)
        if self.version is not None:
            top_limit = self.version.topleft[1] + hud_glow_pad()       # バージョン表記の文字の上端あたり
        else:
            top_limit = None
        try:
            self.assets.fonts.font_for_char(u'\u3042', float(HUD_LOG_FONT_PX) * mult)    # 日本語のフォントを先に読んでおく
        except Exception:
            pass
        for scale in (1.0, max(0.5, float(HUD_LOG_LARGE_SCALE))):
            g = _Bag()
            g.font_px = max(4.0, float(HUD_LOG_FONT_PX) * mult * scale)
            g.pitch = max(4, int(round(g.font_px * float(HUD_LOG_LINE_PITCH))))
            g.text_w = text_w
            g.panel_m = panel_m
            g.glow_pad = glow_pad
            g.text_xy = (p, p)                    # 層の中で、1行目の左上
            if HUD_LOG_LINES is not None:
                n = int(round(int(HUD_LOG_LINES) / scale))
            elif top_limit is not None:
                n = int((bottom - top_limit + glow_pad) // g.pitch)
            else:
                n = int(8 / scale)
            g.n_lines = max(2, n)
            g.size = (g.text_w + 2 * p, g.n_lines * g.pitch + 2 * p)
            g.topleft = (int(left - p), int(bottom - g.n_lines * g.pitch - p))
            self.logs.append(g)
        self.log, self.log_large = self.logs[0], self.logs[1]

    # ---- 板(窓) ----
    def _geos(self):
        extra = [x for x in [self.version] + list(self.logs) + [self.splash] if x is not None]
        return [self.ind] + self.texts + self.row_geo + extra

    def _build_window(self):
        rects = []
        for geo in self._geos():
            tl = geo.topleft
            sz = geo.size
            rects.append((tl[0], tl[1], tl[0] + sz[0], tl[1] + sz[1]))
        if HUD_PLATE_SIZE_M is None:
            mg = max(0, int(round(HUD_PLATE_MARGIN_PX * self.ss)))
            mx = mg + self.extra_margin_x
            wl = min(r[0] for r in rects) - mx
            wt = min(r[1] for r in rects) - mg
            wr = max(r[2] for r in rects) + mx
            wb = max(r[3] for r in rects) + mg
        else:
            pw = max(8, int(round(HUD_PLATE_SIZE_M[0] / self.mpp)))
            ph = max(8, int(round(HUD_PLATE_SIZE_M[1] / self.mpp)))
            wl, wt = -(pw // 2), -(ph // 2)
            wr, wb = wl + pw, wt + ph
        self.window = (wl, wt, wr, wb)
        self.plate_w = wr - wl
        self.plate_h = wb - wt
        self.window_center = ((wl + wr) / 2.0, (wt + wb) / 2.0)
        for geo in self._geos():
            geo.base = (geo.topleft[0] - wl, geo.topleft[1] - wt)


def _hud_vrsystem():
    try:
        return _hud_vrsystem.vrsys
    except AttributeError:
        _hud_vrsystem.vrsys = openvr.VRSystem()
        return _hud_vrsystem.vrsys


class _HudCompositorWatch(object):
    """
    SteamVR の合成 (コンポジター) 自身が vsync に間に合っているかを見る (統計用)。
    合成が遅れる・作り直せないと、ゲームもオーバーレイも (HUD も板の縦線も) まとめてカクつく = こちらでは直せない。
    GetFrameTiming(1 フレーム前 = 確定した値) を描画スレッドのループごとに読み、新しいフレームだけ数える。
    """
    def __init__(self):
        self.ok = True
        self.last_index = None
        self.reset()

    def reset(self):
        self.frames = 0
        self.mispresented = 0        # 遅れて出した (vsync に間に合わなかった) 回数
        self.dropped = 0             # 新しい画面を作れず、前の画面をもう一度出した回数
        self.gpu_sum = 0.0           # 合成の GPU 時間 [ms]
        self.total_gpu_sum = 0.0     # ゲーム + 合成の GPU 時間 [ms]

    def poll(self):
        if not self.ok:
            return
        try:
            ft = self._fn
        except AttributeError:
            try:
                comp = openvr.VRCompositor()
                self._fn = comp.function_table.getFrameTiming
                self._t = openvr.Compositor_FrameTiming()
                self._t.m_nSize = openvr.sizeof(openvr.Compositor_FrameTiming)
            except Exception as e:
                self.ok = False
                print("[HUD Info] SteamVR の合成の統計は取れません: {}: {}".format(type(e).__name__, e))
                return
            ft = self._fn
        try:
            if not ft(openvr.byref(self._t), 1):
                return
        except Exception:
            self.ok = False
            return
        t = self._t
        idx = int(t.m_nFrameIndex)
        if idx == self.last_index:
            return
        self.last_index = idx
        self.frames += 1
        self.mispresented += 1 if int(t.m_nNumMisPresented) > 0 else 0
        self.dropped += 1 if int(t.m_nNumDroppedFrames) > 0 else 0
        self.gpu_sum += float(t.m_flCompositorRenderGpuMs)
        self.total_gpu_sum += float(t.m_flTotalRenderGpuMs)

    def text(self, dt):
        if not self.ok or self.frames <= 0:
            return ""
        n = float(self.frames)
        return " | SteamVR の合成: {:.0f}回/s, 遅れて出した {:.1f}回/s, 前の画面のまま {:.1f}回/s, GPU (全体 {:.1f}ms うち合成 {:.1f}ms)".format(
            n / dt, self.mispresented / dt, self.dropped / dt, self.total_gpu_sum / n, self.gpu_sum / n)


def _hud_vsync_count():
    """SteamVR の vsync の通し番号 (分からなければ None)。"""
    try:
        r = _hud_vrsystem().getTimeSinceLastVsync()
        if isinstance(r, tuple) and len(r) >= 3 and r[0]:
            return int(r[2])
    except Exception:
        pass
    return None


def hud_cycle_shift_switch_vsync():
    """HUD_LATE_SHIFT_SWITCH_VSYNC を 0→1→2→3→0 と変える (コンソールの V キー)。"""
    global HUD_LATE_SHIFT_SWITCH_VSYNC
    HUD_LATE_SHIFT_SWITCH_VSYNC = (int(HUD_LATE_SHIFT_SWITCH_VSYNC) + 1) % 4
    print("[HUD] ずらしの切り替えを、コピー完了から {} vsync 後に (HUD_LATE_SHIFT_SWITCH_VSYNC = {})".format(
        HUD_LATE_SHIFT_SWITCH_VSYNC, HUD_LATE_SHIFT_SWITCH_VSYNC))


def hud_toggle_shift_vsync_target():
    """HUD_LATE_SHIFT_VSYNC_TARGET を入/切 (コンソールの T キー)。"""
    global HUD_LATE_SHIFT_VSYNC_TARGET
    HUD_LATE_SHIFT_VSYNC_TARGET = not HUD_LATE_SHIFT_VSYNC_TARGET
    print("[HUD] ずらしの予測: {} (HUD_LATE_SHIFT_VSYNC_TARGET = {})".format(
        "次に合成される画面が光る時刻に合わせる" if HUD_LATE_SHIFT_VSYNC_TARGET else "常に一定時間先", HUD_LATE_SHIFT_VSYNC_TARGET))


def hud_toggle_dpad_log():
    """DPAD_DEBUG_LOG ([DPAD] の1行ログ) を入/切 (コンソールの O キー。JIT1)。VirtualDPad はこの変数を毎回見る。"""
    global DPAD_DEBUG_LOG
    DPAD_DEBUG_LOG = not DPAD_DEBUG_LOG
    print("[DPAD] 1行ログ: {}".format("出す" if DPAD_DEBUG_LOG else "止める"))


def hud_toggle_pose_thread():
    """HUD_POSE_THREAD を 切 → 姿勢だけ (True) → 全部 ('full') → 切 (コンソールの G キー。0.1.9 / 0.1.11)。"""
    global HUD_POSE_THREAD
    HUD_POSE_THREAD = True if not HUD_POSE_THREAD else ('full' if HUD_POSE_THREAD != 'full' else False)
    print("[HUD] 位置の計算: {}".format({
        False: "描く直前・ずらす直前にその場で計算 (通常)",
        True: "頭の姿勢の予測だけ別スレッド (描く側は代入された姿勢から計算)",
        'full': "全部別スレッド (写し方・拡大縮小・ずらし。描く側は代入された写し方を読むだけ)"}[HUD_POSE_THREAD]))


def hud_toggle_fixed_ref():
    """HUD_FIXED_REF を入/切 (コンソールの B キー。0.1.13)。"""
    global HUD_FIXED_REF
    HUD_FIXED_REF = not HUD_FIXED_REF
    print("[HUD] 基準の目で描く (HUD_FIXED_REF): {}".format(
        "入 (絵は基準の目の形のまま、頭の動きはずらしで直す)" if HUD_FIXED_REF else "切 (絵を今の頭の位置で描く。通常)"))


def hud_toggle_crosshair():
    """HUD_DEBUG_CROSSHAIR を入/切 (コンソールの U キー。0.1.13)。"""
    global HUD_DEBUG_CROSSHAIR
    HUD_DEBUG_CROSSHAIR = not HUD_DEBUG_CROSSHAIR
    print("[HUD] 基準の十字線: {}".format("出す" if HUD_DEBUG_CROSSHAIR else "隠す"))


def hud_toggle_late_shift():
    """HUD_LATE_SHIFT を入/切 (コンソールの K キー。JIT1)。切ると次の描画で遠いオーバーレイは元の位置に戻る。"""
    global HUD_LATE_SHIFT
    HUD_LATE_SHIFT = not HUD_LATE_SHIFT
    print("[HUD] ずらし (HUD_LATE_SHIFT): {}".format("入" if HUD_LATE_SHIFT else "切"))


def hud_cycle_texture_freeze():
    """HUD_TEXTURE_FREEZE_HZ を HUD_TEXTURE_FREEZE_STEPS の順に変える (コンソールの X キー。JIT1)。"""
    global HUD_TEXTURE_FREEZE_HZ
    steps = [float(v) for v in HUD_TEXTURE_FREEZE_STEPS] or [0.0]
    cur = float(HUD_TEXTURE_FREEZE_HZ or 0.0)
    i = steps.index(cur) if cur in steps else -1
    HUD_TEXTURE_FREEZE_HZ = steps[(i + 1) % len(steps)]
    if HUD_TEXTURE_FREEZE_HZ > 0.0:
        print("[HUD] 絵の描き直しを {:g} 回/秒に絞る (ずらしはそのまま。'fakefar' + ずらし入 のときだけ効く)".format(HUD_TEXTURE_FREEZE_HZ))
    else:
        print("[HUD] 絵の描き直し: 通常")


class _HudJitterCsv(object):
    """
    HUD 揺れ調査用の CSV (JIT1)。HUD の描画スレッドから row() で1行ずつためて、HUD_JITTER_CSV_FLUSH_SEC ごとにまとめて書く。
    start/stop はキーの処理 (Joystick.update のスレッド) から呼ばれるので、ためる所は lock で守る。
    """
    COLUMNS = ['t_ms', 'clock', 'event', 'vsync', 'pose_age_ms', 'gpu_wait_ms', 'since_submit_ms',
               'ref_x_mm', 'ref_y_mm', 'eye_x_mm', 'eye_y_mm', 'dx_mm', 'dy_mm', 'lead_ms']

    def __init__(self):
        self._lock = threading.Lock()
        self._f = None
        self._buf = []
        self._t0 = 0.0
        self._t_flush = 0.0
        self.path = None

    @property
    def on(self):
        return self._f is not None

    def start(self):
        if self._f is not None:
            return
        try:
            d = HUD_JITTER_CSV_DIR or os.path.dirname(os.path.abspath(__file__))
            self.path = os.path.join(d, time.strftime('hud_jitter_%Y%m%d_%H%M%S.csv'))
            f = open(self.path, 'w')
            f.write(','.join(self.COLUMNS) + '\n')
            with self._lock:
                self._buf = []
                self._t0 = time.time()
                self._t_flush = self._t0
                self._f = f
            print("[HUD] 調査用 CSV の記録を始めました: {}".format(self.path))
        except Exception as e:
            self._f = None
            print("[HUD Error] 調査用 CSV を開けません: {}: {}".format(type(e).__name__, e))

    def stop(self):
        with self._lock:
            f, self._f = self._f, None
            buf, self._buf = self._buf, []
        if f is None:
            return
        try:
            f.write(''.join(buf))
            f.close()
            print("[HUD] 調査用 CSV の記録を止めました: {}".format(self.path))
        except Exception as e:
            print("[HUD Error] 調査用 CSV を書けません: {}: {}".format(type(e).__name__, e))

    def row(self, event, **kw):
        """1行ためる。kw の名前は COLUMNS の名前 (無いものは空欄)。数値は小数3桁。"""
        if self._f is None:
            return
        now = time.time()
        kw['t_ms'] = (now - self._t0) * 1000.0
        kw['clock'] = time.strftime('%H:%M:%S', time.localtime(now)) + '.{:03d}'.format(int((now % 1.0) * 1000.0))
        kw['event'] = event
        if 'vsync' not in kw:
            kw['vsync'] = _hud_vsync_count()
        cells = []
        for c in self.COLUMNS:
            v = kw.get(c)
            if v is None:
                cells.append('')
            elif isinstance(v, float):
                cells.append('{:.3f}'.format(v))
            else:
                cells.append(str(v))
        line = ','.join(cells) + '\n'
        with self._lock:
            if self._f is None:
                return
            self._buf.append(line)
            if now - self._t_flush < float(HUD_JITTER_CSV_FLUSH_SEC):
                return
            self._t_flush = now
            buf, self._buf = self._buf, []
            try:
                self._f.write(''.join(buf))
            except Exception as e:
                print("[HUD Error] 調査用 CSV を書けません: {}: {}".format(type(e).__name__, e))


HUD_JITTER_CSV = _HudJitterCsv()
atexit.register(HUD_JITTER_CSV.stop)


def hud_toggle_jitter_csv():
    """調査用 CSV の記録を始める / 止める (コンソールの J キー。JIT1)。"""
    if HUD_JITTER_CSV.on:
        HUD_JITTER_CSV.stop()
    else:
        HUD_JITTER_CSV.start()


def _hud_display_timing():
    """(1フレームの秒数, vsync から光るまでの秒数)。1回だけ SteamVR に聞いて覚える。"""
    try:
        return _hud_display_timing.cache
    except AttributeError:
        pass
    vrsys = _hud_vrsystem()

    def prop(p, default):
        try:
            r = vrsys.getFloatTrackedDeviceProperty(openvr.k_unTrackedDeviceIndex_Hmd, p)
            v = r[0] if isinstance(r, tuple) else r          # 旧版は (値, エラー) を返す
            v = float(v)
            return v if v > 0 else default
        except Exception:
            return default
    hz = prop(openvr.Prop_DisplayFrequency_Float, 90.0)
    photons = prop(openvr.Prop_SecondsFromVsyncToPhotons_Float, 0.011)
    _hud_display_timing.cache = (1.0 / max(30.0, hz), min(0.05, photons))
    return _hud_display_timing.cache


def hud_auto_predict_sec():
    """
    「今描いた HUD が実際に目に見える瞬間」までの秒数。その瞬間の頭の位置で描けば、頭を振っても HUD が遅れて見えにくい。
    = (次の vsync まで) + (vsync から光るまで) + HUD_DEPTH_PREDICT_EXTRA_SEC
    """
    frame, photons = _hud_display_timing()
    since = 0.0
    try:
        r = _hud_vrsystem().getTimeSinceLastVsync()
        if isinstance(r, tuple) and r[0]:
            since = float(r[1])
    except Exception:
        pass
    to_vsync = frame - (since % frame)
    return max(0.0, min(0.1, to_vsync + photons + float(HUD_DEPTH_PREDICT_EXTRA_SEC)))


def _hud_fine_timer():
    """Windows の sleep を 1ms 単位にする (既定だと最大 15ms ずれ、描くタイミングがばらつく)。"""
    try:
        import ctypes
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


def _hud_raise_thread_priority():
    """今のスレッドの優先度を上げ (Windows: THREAD_PRIORITY_HIGHEST)、Python のスレッド切り替えを 1ms ごとにする。"""
    import sys
    try:
        if sys.getswitchinterval() > 0.001:
            sys.setswitchinterval(0.001)
    except Exception:
        pass
    if os.name != 'nt':
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetThreadPriority(k32.GetCurrentThread(), 2)
        print("[HUD] 描画スレッドの優先度を上げました")
    except Exception as e:
        print("[HUD Warning] 描画スレッドの優先度を上げられません: {}: {}".format(type(e).__name__, e))


def _hud_wait_next_frame():
    """次の vsync の少し後まで待つ。画面の更新1回につき HUD を1回描くため。分からなければ HUD_MAX_FPS で待つ。"""
    try:
        frame, _ = _hud_display_timing()
        r = _hud_vrsystem().getTimeSinceLastVsync()
        if isinstance(r, tuple) and r[0]:
            since = float(r[1]) % frame
            wait = frame - since + float(HUD_RENDER_AFTER_VSYNC_SEC)
            if wait > frame:
                wait -= frame
            time.sleep(max(0.0005, wait))
            return
    except Exception:
        pass
    time.sleep(1.0 / max(10.0, float(HUD_MAX_FPS)))


def _hud_pose_from_matrix(m):
    pos = (m[0][3], m[1][3], m[2][3])
    rot = tuple(tuple(m[i][j] for j in range(3)) for i in range(3))
    return pos, rot


def _hud_m34(m):
    """HmdMatrix34_t → ((r00..r22), (tx, ty, tz)) の Python の値。"""
    return (tuple(tuple(float(m[i][j]) for j in range(3)) for i in range(3)),
            (float(m[0][3]), float(m[1][3]), float(m[2][3])))


def _hud_apply_inv(tf, pos, rot):
    """剛体変換 tf = (R, t) の逆を、姿勢 (pos, rot) に掛ける: R^T (pos - t), R^T rot。"""
    R, tr = tf
    d = [pos[i] - tr[i] for i in range(3)]
    p2 = tuple(sum(R[k][i] * d[k] for k in range(3)) for i in range(3))
    r2 = tuple(tuple(sum(R[k][i] * rot[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return p2, r2


def _hud_apply(tf, pos, rot):
    """剛体変換 tf = (R, t) を姿勢 (pos, rot) に掛ける: R pos + t, R rot。"""
    R, tr = tf
    p2 = tuple(sum(R[i][k] * pos[k] for k in range(3)) + tr[i] for i in range(3))
    r2 = tuple(tuple(sum(R[i][k] * rot[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return p2, r2


class _HudPoseReader(object):
    """
    頭の位置を読む。HUD_POSE_SOURCE = 'game' なら、ゲーム (シーンアプリ) が今描いている画面の頭の位置
    (IVRCompositor::GetLastPoseForTrackedDeviceIndex の描画用の姿勢) を使う。
    ゲームの FPS が低いと、景色は「ゲームが描いたときの頭の位置」で見え、SteamVR / Virtual Desktop は向きしか補正しない。
    HUD もそれと同じ頭の位置で描けば、景色 (コックピット) と HUD がずれない。
    取れない・0.25 秒以上変わらない (ゲームが止まっている) ときは予測した位置を使う。
    """
    MAX_DIFF_M = 0.5         # 予測した位置とこれ以上離れていたら、変換がおかしいとみなす
    BAD_FRAMES = 30          # その状態がゲームのフレームでこれだけ続いたら予測に切り替える
    XFORM_REFRESH_SEC = 0.0  # 座標の変換を取り直す間隔。0 = 毎回 (プレイスペースムーバーなどで動き続けるため)

    def __init__(self):
        self.comp = None
        self.comp_failed = False
        self._xf = None
        self._xf_time = -1e9
        self._bad_reported = False
        self._bad = 0
        self.frames = 0
        self.last_key = None
        self.last_change = 0.0
        self.source = None        # 実際に使っている方 ('game' / 'predict')

    def _game(self):
        if self.comp_failed:
            return None
        try:
            if self.comp is None:
                self.comp = openvr.VRCompositor()
            r = self.comp.getLastPoseForTrackedDeviceIndex(openvr.k_unTrackedDeviceIndex_Hmd)
            if len(r) == 3:
                result, pose = r[0], r[1]          # 同梱の旧版 (1.0.0701): (結果, 描画用の姿勢, ゲーム用の姿勢)
            else:
                result, pose = 0, r[0]             # 新しい版 (2.x): (描画用の姿勢, ゲーム用の姿勢)。失敗は例外
            if result != 0 or not pose.bPoseIsValid:
                return None
            pos, rot = _hud_pose_from_matrix(pose.mDeviceToAbsoluteTracking.m)
            out = self._to_seated(pos, rot)
            self._fails = 0
            return out
        except Exception as e:
            self._fails = getattr(self, '_fails', 0) + 1
            self._xf = None
            if self._fails >= 5:          # 続けて失敗するなら、あきらめて予測だけを使う
                self.comp_failed = True
                print("[HUD Warning] ゲームの頭の位置を読めません ({}: {}) -> 予測を使います".format(type(e).__name__, e))
            return None

    def _to_seated(self, pos, rot):
        """
        ゲームの姿勢は、ゲームが使う座標 (VRChat なら立って使う座標 = 床が基準) で返ってくる。
        HUD は座って使う座標 (着座位置が基準) なので変換する。
        """
        now = time.time()
        if self._xf is None or now - self._xf_time > self.XFORM_REFRESH_SEC:
            self._xf_time = now
            vrsys = _hud_vrsystem()
            space = int(self.comp.getTrackingSpace())
            seated = _hud_m34(vrsys.getSeatedZeroPoseToStandingAbsoluteTrackingPose().m)   # 着座 → 立ち
            raw = None
            if space == int(openvr.TrackingUniverseRawAndUncalibrated):
                raw = _hud_m34(vrsys.getRawZeroPoseToStandingAbsoluteTrackingPose().m)      # 生 → 立ち
            self._xf = (space, seated, raw)
        space, seated, raw = self._xf
        if space == int(openvr.TrackingUniverseSeated):
            return pos, rot
        if raw is not None:
            pos, rot = _hud_apply(raw, pos, rot)          # 生 → 立ち
        return _hud_apply_inv(seated, pos, rot)          # 立ち → 着座

    def read(self, predict_sec):
        """
        'game' のときは、取れる限りゲームの姿勢を使い続ける (予測との行き来は、そのたびに HUD が跳ぶので避ける)。
        ゲームが止まっていても (読み込み中など)、画面もその姿勢のまま止まっているので、同じ姿勢で描くのが正しい。
        予測に切り替えるのは、姿勢が取れない・HUD_GAME_POSE_STALE_SEC 以上変わらない (ゲームがない)・
        座標の変換が明らかにおかしい状態が続いたとき だけ。
        """
        if str(HUD_POSE_SOURCE) in ('game', 'hybrid'):
            g = self._game()
            now = time.time()
            if g is not None:
                key = g[0] + g[1][0]
                if key != self.last_key:
                    self.last_key = key
                    self.last_change = now
                    self.frames += 1          # 気づいたゲームのフレームの数 (統計用)
                    # 念のため: 予測した位置と大きく離れた状態が続くなら (座標の変換がおかしい) 使わない
                    #   (新しいフレームのときだけ確かめる。一瞬の食い違いでは切り替えない)
                    try:
                        p = _read_head_pose(predict_sec)
                        diff = math.sqrt(sum((g[0][i] - p[0][i]) ** 2 for i in range(3))) if p else 0.0
                    except Exception:
                        diff = 0.0
                    self._bad = self._bad + 1 if diff > self.MAX_DIFF_M else 0
                    if self._bad == self.BAD_FRAMES and not self._bad_reported:
                        self._bad_reported = True
                        print("[HUD Warning] ゲームの頭の位置が予測と {:.2f}m 違う状態が続いています (座標が合わない) -> 予測を使います".format(diff))
                if self._bad < self.BAD_FRAMES and now - self.last_change < float(HUD_GAME_POSE_STALE_SEC):
                    self._report('game')
                    return g
        self._report('display' if str(HUD_POSE_SOURCE) == 'display' else 'predict')
        return _read_head_pose(predict_sec)

    def _report(self, src):
        if src != self.source:
            self.source = src
            print("[HUD] 頭の位置: {}".format({
                'game': "ゲームが描画に使った位置 (game)",
                'display': "最新の予測 (display: ゲームの姿勢は使わない)",
            }.get(src, "予測した位置 (predict)")))


_HUD_POSE = _HudPoseReader()


def hud_adjust_predict_extra(delta):
    """
    HUD_DEPTH_PREDICT_EXTRA_SEC を実行中に変える (コンソールの [ / ] キーで 2ms ずつ、\\ キーで 0 に戻す)。
    SteamVR が HUD の絵を読む時刻が想定とずれていると、頭を動かしたとき仮想 far の位置合わせが
    vsync ごとに段差になって見える。そのときは、揺れが一番小さくなる値を探して [CONFIG] に書く。
    """
    global HUD_DEPTH_PREDICT_EXTRA_SEC
    if delta is None:
        HUD_DEPTH_PREDICT_EXTRA_SEC = 0.0
    else:
        HUD_DEPTH_PREDICT_EXTRA_SEC = round(float(HUD_DEPTH_PREDICT_EXTRA_SEC) + delta, 4)
    try:
        frame, _ = _hud_display_timing()
        fr = " (1フレーム = {:.1f}ms)".format(frame * 1000.0)
    except Exception:
        fr = ""
    print("[HUD] 予測に足す時間 HUD_DEPTH_PREDICT_EXTRA_SEC = {:+.3f} 秒{}".format(HUD_DEPTH_PREDICT_EXTRA_SEC, fr))
    if HUD_DISPLAY_CONTINUOUS and str(HUD_POSE_SOURCE) == 'display':
        try:
            frame, photons = _hud_display_timing()
            base = float(HUD_DISPLAY_PREDICT_SEC) if HUD_DISPLAY_PREDICT_SEC is not None else 0.5 * frame + photons
            print("[HUD]   → 'display' の先読み = {:.1f}ms".format(1000.0 * max(0.0, base + HUD_DEPTH_PREDICT_EXTRA_SEC)))
        except Exception:
            pass


def hud_tracking_diagnose(seconds=3.0):
    """
    頭の姿勢がどう届いているかを測ってコンソールに出す (コンソールの D キー。別スレッドで動く)。
      ・ドライバーから新しい姿勢が届く回数 [回/秒] (先読みなしで読んだ値が変わった回数)
      ・ドライバーが送ってくる速度の大きさ (0 なら先読みが効かない)
      ・先読み 50ms と 0ms の位置の差 (頭を動かしているのに 0 なら先読みが効いていない)
    測っている間は、頭をゆっくり左右に動かし続けること。
    """
    def run():
        try:
            vrsys = _hud_vrsystem()

            def pose(pred):
                try:
                    ps = vrsys.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, pred, 1)
                except TypeError:
                    ps = (openvr.TrackedDevicePose_t * 1)()
                    vrsys.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, pred, ps)
                return ps[0]
            print("[HUD 診断] {:.1f} 秒間測ります。頭をゆっくり左右に動かし続けてください".format(seconds))
            t0 = time.time()
            last = None
            changes = 0
            reads = 0
            vel_sum = 0.0
            diff_sum = 0.0
            moving = 0.0
            while time.time() - t0 < seconds:
                p0 = pose(0.0)
                p50 = pose(0.05)
                m0 = p0.mDeviceToAbsoluteTracking.m
                pos0 = (m0[0][3], m0[1][3], m0[2][3])
                m5 = p50.mDeviceToAbsoluteTracking.m
                pos5 = (m5[0][3], m5[1][3], m5[2][3])
                v = p0.vVelocity.v
                vel = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
                reads += 1
                if last is not None and pos0 != last:
                    changes += 1
                    moving += math.sqrt(sum((pos0[i] - last[i]) ** 2 for i in range(3)))
                last = pos0
                vel_sum += vel
                diff_sum += math.sqrt(sum((pos5[i] - pos0[i]) ** 2 for i in range(3)))
                time.sleep(0.0005)
            dt = time.time() - t0
            n = max(1, reads)
            print("[HUD 診断] 新しい姿勢が届いた回数 {:.0f} 回/秒 (読んだ回数 {:.0f} 回/秒) | 頭の移動 合計 {:.3f}m".format(
                changes / dt, reads / dt, moving))
            print("[HUD 診断] ドライバーの速度 平均 {:.3f} m/s | 先読み 50ms と 0ms の位置の差 平均 {:.1f} mm".format(
                vel_sum / n, 1000.0 * diff_sum / n))
            if moving > 0.01 and diff_sum / n < 0.0005:
                print("[HUD 診断] → 頭は動いているのに先読みで位置が変わりません。ドライバーが速度を送っていないため、"
                      "先読み (HUD_DEPTH_PREDICT_*) は効きません")
        except Exception as e:
            print("[HUD 診断] 測れませんでした: {}: {}".format(type(e).__name__, e))
    th = threading.Thread(target=run, name='hud_diag')
    th.daemon = True
    th.start()


def _read_head_pose(predict_sec=0.0):
    """
    頭(HMD)の 位置 (x, y, z) [m] と 向き (3x3 行列) をシート座標で返す。取れなければ None。
    predict_sec = None なら hud_auto_predict_sec() で先読みする。
    """
    vrsys = _hud_vrsystem()
    if predict_sec is None:
        predict_sec = hud_auto_predict_sec()
    try:
        poses = vrsys.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, predict_sec, 1)    # 同梱の旧版 (1.0.0701)
    except TypeError:
        poses = (openvr.TrackedDevicePose_t * 1)()                                                       # 新しい版 (2.x)
        vrsys.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseSeated, predict_sec, poses)
    pose = poses[0]
    if not pose.bPoseIsValid:
        return None
    m = pose.mDeviceToAbsoluteTracking.m
    pos = (m[0][3], m[1][3], m[2][3])
    rot = tuple(tuple(m[i][j] for j in range(3)) for i in range(3))
    return pos, rot


def _read_eye_offsets():
    """頭の中心から 左目・右目 までのずれ (頭の座標, [m])。"""
    vrsys = _hud_vrsystem()
    out = []
    for eye in (openvr.Eye_Left, openvr.Eye_Right):
        m = vrsys.getEyeToHeadTransform(eye).m
        out.append((m[0][3], m[1][3], m[2][3]))
    return out


class HudDepth(object):
    """
    奥行き(視差)専用の計算。描画も OpenVR の表示も知らない。板(オーバーレイ)は動かさず、
    「板の上で HUD の絵をどれだけ拡大し、どこへずらして描くか」= 写し方 (s, ox, oy) を目ごとに返す。
        板の上の点 c (シート座標 x, y [m])  →  s * c + (ox, oy)  に描く

    考え方 (光学照準器 / SACC の HUD と同じ。SACC は HUD の記号を本当に遠くに置き、
            ガラス面のステンシルで切り抜いている。ここでは同じ見え方を、目ごとの描き直しで作る):
      ・HUD の絵は、基準の目 E0 から見て板とぴったり重なる「虚像」として、板より distance 奥にある。
      ・目 E (左目・右目それぞれ) と虚像を結ぶ線が板を通る点に描く。左右の目で描く位置が違うので
        両目の寄り具合も虚像の距離に合い、本当に遠くに見える (HUD_STEREO)。
      ・keep_size=True : 虚像は頭から前後に一定の距離を保つ → 近づいても離れても見た目の大きさは一定。
                          左右上下は空間に固定なので、頭を動かすと視差が出る。
        keep_size=False: 虚像は空間に固定 (普通の物体と同じ)。
      ・E0 は「HUD の基準点 (HUD_PLATE_POS) + HUD_DEPTH_EYE_OFFSET」で固定 (両目の真ん中)。
      ・目が板を越えたら、clamp_near=False なら前の絵のまま止める。True なら最小距離に押さえる。
    """
    NEAR_LIMIT = 0.05       # 目と板の距離がこれ未満なら「板を越えた」とみなす [m]
    CLAMP_DIST = 0.15       # clamp_near=True のときに押さえる最小距離 [m]
    DEFAULT_IPD = 0.063
    EYE_REFRESH_SEC = 2.0   # 目の間隔 (IPD) を取り直す間隔

    def __init__(self, enabled, distance_m, keep_size, eye_offset, clamp_near=False, predict_sec=0.0,
                 head_getter=None, eye_getter=None, ipd=None):
        self.enabled = bool(enabled)
        self.distance = max(0.0, float(distance_m))
        self.keep_size = bool(keep_size)
        self.eye_offset = tuple(float(v) for v in eye_offset)
        self.clamp_near = bool(clamp_near)
        self.predict = None if predict_sec is None else float(predict_sec)   # None = 自動
        self._get = head_getter or (lambda: _HUD_POSE.read(self.predict))
        self._get_eyes = eye_getter or _read_eye_offsets
        self.ipd = ipd
        self.head = None
        self.rot = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
        self.eye_local = [(-self.DEFAULT_IPD / 2.0, 0.0, 0.0), (self.DEFAULT_IPD / 2.0, 0.0, 0.0)]
        self._eye_time = -1e9
        self._fails = 0
        self._dead = False

    def is_active(self):
        return self.enabled and not self._dead

    def set_distance(self, meters):
        self.distance = max(0.0, float(meters))

    def update(self):
        """頭の位置・向きを読む。5回続けて失敗したら奥行き表示を止める (HUD 自体は表示を続ける)。"""
        if not self.is_active():
            return
        try:
            p = self._get()
            self._fails = 0
        except Exception as e:
            p = None
            self._fails += 1
            if self._fails == 5:
                print("[HUD Warning] 頭の位置を読めません (奥行き表示を止めます): {}: {}".format(type(e).__name__, e))
                self._dead = True
        if p is None:
            return
        if len(p) == 2:
            pos, rot = p
        else:
            pos, rot = p, None                           # 位置だけ (テスト用)
        if all(v == v and abs(v) < 1e6 for v in pos):
            self.head = (float(pos[0]), float(pos[1]), float(pos[2]))
            if rot is not None:
                self.rot = rot
        self._refresh_eyes()

    def _refresh_eyes(self):
        now = time.time()
        if now - self._eye_time < self.EYE_REFRESH_SEC:
            return
        self._eye_time = now
        if self.ipd is not None:
            h = float(self.ipd) / 2.0
            self.eye_local = [(-h, 0.0, 0.0), (h, 0.0, 0.0)]
            return
        try:
            eyes = self._get_eyes()
            if eyes and 0.04 < abs(eyes[1][0] - eyes[0][0]) < 0.09:
                self.eye_local = [tuple(float(v) for v in e) for e in eyes]
        except Exception:
            pass

    def eye_positions(self, stereo):
        """目の位置 (シート座標)。stereo=True なら [左目, 右目]、False なら [頭の中心]。"""
        if self.head is None:
            return None
        return self.eyes_from(self.head, self.rot, stereo)

    def eyes_from(self, head, rot, stereo):
        """頭の位置・向きから目の位置を出す (eye_positions と同じ計算を、好きな姿勢で)。"""
        if not stereo:
            return [tuple(head)]
        R, h = rot, head
        out = []
        for e in self.eye_local:
            out.append(tuple(h[i] + R[i][0] * e[0] + R[i][1] * e[1] + R[i][2] * e[2] for i in range(3)))
        return out

    def ipd_now(self):
        e = self.eye_local
        return math.sqrt(sum((e[1][i] - e[0][i]) ** 2 for i in range(3)))

    def offset_from(self, ref_point):
        """今の頭の位置を、HUD の基準点からの (右, 上, 手前) [m] で返す (HUD_DEPTH_EYE_OFFSET に書く値)。"""
        if self.head is None:
            return None
        return tuple(self.head[i] - ref_point[i] for i in range(3))

    def mapping(self, ref_point, eye):
        """
        目 eye から見た写し方 (s, ox, oy) を返す。None = 目が板を越えたので前の絵のまま。
        ref_point = HUD の基準点 (x, y, z) [m]。板の面は z = ref_point[2]。
        """
        rx, ry, pz = ref_point
        e0x, e0y = rx + self.eye_offset[0], ry + self.eye_offset[1]
        ez0 = max(self.eye_offset[2], self.NEAR_LIMIT)          # 基準の目から板まで
        ex, ey, ez_abs = eye
        ez = ez_abs - pz                                         # この目から板まで
        if ez < self.NEAR_LIMIT:
            if not self.clamp_near:
                return None
            ez = self.CLAMP_DIST
        big_d = ez0 + self.distance                              # 基準の目から虚像まで
        to_virtual = big_d if self.keep_size else ez + self.distance   # この目から虚像までの前後の距離
        f = ez / to_virtual                                      # 虚像 → 板 への縮め方
        s = f * big_d / ez0
        ox = ex * (1.0 - f) + f * e0x - s * e0x
        oy = ey * (1.0 - f) + f * e0y - s * e0y
        return (s, ox, oy)


class HudNoticeBoard(object):
    """
    システム通知インジゲータ専用 (描画を知らない)。段(row)ごとに
      ・どの信号 ('vbtn:22' など) が押されたら出すか ('on')
      ・消えるまでの残り時間 ('hold_sec')
      ・どんな状況で色を変えるか ('color_rules')
    を持ち、update() で「どの段が・何色で出ているか」を返す。信号は set_signals() で外から渡す。
    """

    def __init__(self, rows):
        self.rows = rows
        self._sig = {}
        n = len(rows)
        self._active = [False] * n
        self._until = [0.0] * n
        self._color = [None] * n

    def set_signals(self, mapping):
        for k, v in mapping.items():
            self._sig[k] = bool(v)

    def is_any(self, names):
        for n in names:
            if self._sig.get(n, False):
                return True
        return False

    def _resolve_color(self, row):
        if not row['uses_color']:
            return None
        for rule in row['color_rules']:
            if self.is_any(rule['when']):
                return rule['color']
        return row['color']

    def update(self, now):
        key = []
        for i, row in enumerate(self.rows):
            if self.is_any(row['on']):
                self._active[i] = True
                self._until[i] = now + row['hold_sec']
                self._color[i] = self._resolve_color(row)
            elif self._active[i] and now >= self._until[i]:
                self._active[i] = False
            key.append((self._active[i], self._color[i] if self._active[i] else None))
        return tuple(key)


class _HudLayer(object):
    """板の中の1つの部品(層)。絵と位置を覚えておき、変わったところだけ書き直す。"""

    def __init__(self, kind, size, base, index=None, static_img=None):
        self.kind = kind                 # 'indicator' / 'text' / 'row' / 'log'
        self.size = size
        self.base = base                 # 板の中での基準位置 (視差のずれを足す前)
        self.index = index
        self.static_img = static_img
        self.img = None
        self.rect = None                 # 今、板に描いている範囲
        self.state = None


class HudGLContext(object):
    """
    HUD 用の OpenGL 環境 (見えない glfw ウィンドウ1つ)。オーバーレイを何枚作っても共有する。
    使う側は acquire() で受け取り、終わったら release()。最後の release で片付ける。
    """
    _shared = None

    def __init__(self):
        import ctypes
        import glfw
        from OpenGL import GL
        self.ct, self.glfw, self.GL = ctypes, glfw, GL
        self.users = 0
        if not glfw.init():
            raise RuntimeError("glfw.init() failed")
        glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
        self.win = glfw.create_window(64, 64, "hud_gl", None, None)
        if not self.win:
            glfw.terminate()
            raise RuntimeError("could not create GL context")
        glfw.make_context_current(self.win)

    @classmethod
    def acquire(cls):
        if cls._shared is None:
            cls._shared = HudGLContext()
        cls._shared.users += 1
        return cls._shared

    def make_current(self):
        self.glfw.make_context_current(self.win)

    def release(self):
        self.users -= 1
        if self.users <= 0 and HudGLContext._shared is self:
            HudGLContext._shared = None
            try:
                self.glfw.destroy_window(self.win)
                self.glfw.terminate()
            except Exception:
                pass


class HudGfx(object):
    """
    描画の裏方 (バックエンド) の決まりごと。HudPlateOverlay は GPU をこのメソッドだけで使う
    (OpenGL の関数を直接呼ばない)。D3D11 などを足すときは、これを継承したクラスを作り、
    HUD_GFX_BACKEND で選べるようにする (_hud_make_gfx)。

    座標の約束 (バックエンドによらない):
      - 画像 (PIL, RGBA, 上が先頭の行) をそのまま upload に渡す。上下の並べ替えはバックエンドの仕事。
      - 出力への描画座標は「板の px」(左上が原点、右+、下+、0..coord_w / 0..coord_h)。
      - 切り抜き (clip) は「その目の出力テクスチャの px」(左上原点) の (x0, y0, x1, y1)。
      - 出力テクスチャは目の数だけ横に並ぶ (左目 = 左半分)。set_eye(i) で描く目を選ぶ。
    テクスチャ・出力・フェンスは中身の分からない値 (ハンドル) として扱う。
    """
    name = 'base'
    texture_type = None            # openvr.TextureType_xxx (SteamVR に渡すときの種類)

    def make_current(self):
        """描くスレッドで使えるようにする (スレッドを移るとき)。"""

    def detach(self):
        """このスレッドから外す (別のスレッドに渡す前)。"""

    def close(self):
        raise NotImplementedError

    def new_texture(self, w, h, mipmap=False, lod_bias=None):
        """空の RGBA テクスチャ。mipmap=True なら縮小用の段 (HUD_MIPMAP_MAX_LEVEL まで)。lod_bias = 段を粗い側へ寄せる量。"""
        raise NotImplementedError

    def set_mipmap(self, tex, on):
        raise NotImplementedError

    def upload(self, tex, img, px, py, tex_h):
        """テクスチャ (高さ tex_h) の (px, py) [左上] に PIL 画像 img を書き込む。"""
        raise NotImplementedError

    def gen_mipmap(self, tex):
        raise NotImplementedError

    def delete_texture(self, tex):
        raise NotImplementedError

    def new_output(self, w, h):
        """描き込み先 (出力テクスチャ)。作れなければ例外。"""
        raise NotImplementedError

    def output_texture(self, out):
        """出力の、SteamVR に渡すテクスチャのハンドル (Texture_t.handle にする値)。"""
        raise NotImplementedError

    def delete_output(self, out):
        raise NotImplementedError

    def begin_output(self, out, coord_w, coord_h, pix_w, pix_h, n_eyes):
        """out に描き始める (透明で消す)。coord = 板の px の広さ、pix = 1つの目の出力の px。"""
        raise NotImplementedError

    def set_eye(self, i):
        raise NotImplementedError

    def draw_textured(self, tex, x0, y0, x1, y1, clip=None):
        """tex 全体を板の px の四角 (x0, y0)-(x1, y1) に描く (混ぜずに上書き)。clip = 目の出力 px の切り抜き。"""
        raise NotImplementedError

    def fill_rect(self, color, x0, y0, x1, y1):
        """color (0..255 の RGBA) で板の px の四角を塗る。"""
        raise NotImplementedError

    def end_output(self, out):
        """描き終わり (出力のミップマップもここで作る)。"""
        raise NotImplementedError

    def fence(self):
        """ここまでの GPU の仕事の後ろに目印を置き、GPU に送る。使えなければ None。"""
        return None

    def fence_done(self, token):
        """目印まで GPU が終わったか (待たない)。失敗も True (待ち続けないため)。"""
        return True

    def fence_delete(self, token):
        pass

    def finish(self):
        """GPU が全部終わるまで待つ。"""
        raise NotImplementedError

    def drain_errors(self):
        """溜まっているエラーの番号のリスト (SteamVR がこちらの環境で出したものを取り除く)。"""
        return []

    def submit(self, fn_texture, handle, texture_struct):
        """SteamVR の SetOverlayTexture を呼ぶ (ctypes の参照渡しはバックエンドの環境で)。"""
        return fn_texture(handle, openvr.byref(texture_struct))


class HudGfxOpenGL(HudGfx):
    """
    OpenGL (glfw の見えないウィンドウ + 固定機能の glBegin/glEnd)。今の既定。
    SteamVR へは TextureType_OpenGL で渡す。OpenGL の慣習どおりメモリの1行目 = 絵の下端 (FLIP_Y)。
    """
    name = 'opengl'
    FLIP_Y = True               # 表示が上下逆さまなら False にする

    def __init__(self):
        self.ctx = HudGLContext.acquire()
        self.GL = self.ctx.GL
        self.ctx.make_current()
        self.GL.glPixelStorei(self.GL.GL_UNPACK_ALIGNMENT, 1)
        self.texture_type = openvr.TextureType_OpenGL
        self._fence_ok = True
        self._cur = None             # 描いている出力 (fbo, tex, eye_w, eye_h)

    def make_current(self):
        self.ctx.make_current()

    def detach(self):
        self.ctx.glfw.make_context_current(None)

    def close(self):
        if self.ctx is not None:
            self.ctx.release()
            self.ctx = None

    def new_texture(self, w, h, mipmap=False, lod_bias=None):
        GL = self.GL
        tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        mipmap = mipmap and int(HUD_MIPMAP_MAX_LEVEL) > 0
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER,
                           GL.GL_LINEAR_MIPMAP_LINEAR if mipmap else GL.GL_LINEAR)
        if mipmap:
            # 縮小しすぎてぼやけないよう、使う段の上限を決める
            GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAX_LEVEL, int(HUD_MIPMAP_MAX_LEVEL))
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, w, h, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        if lod_bias is not None:
            try:
                GL.glTexParameterf(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_LOD_BIAS, float(lod_bias))
            except Exception:
                pass
        return tex

    def set_mipmap(self, tex, on):
        GL = self.GL
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER,
                           GL.GL_LINEAR_MIPMAP_LINEAR if on else GL.GL_LINEAR)

    def upload(self, tex, img, px, py, tex_h):
        GL = self.GL
        w, h = img.size
        if self.FLIP_Y:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            py = tex_h - (py + h)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexSubImage2D(GL.GL_TEXTURE_2D, 0, int(px), int(py), w, h,
                           GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, img.tobytes())

    def gen_mipmap(self, tex):
        GL = self.GL
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glGenerateMipmap(GL.GL_TEXTURE_2D)

    def delete_texture(self, tex):
        if tex is not None:
            self.GL.glDeleteTextures([tex])

    def new_output(self, w, h):
        GL = self.GL
        tex = self.new_texture(w, h, mipmap=True)
        fbo = GL.glGenFramebuffers(1)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, fbo)
        GL.glFramebufferTexture2D(GL.GL_FRAMEBUFFER, GL.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, tex, 0)
        status = GL.glCheckFramebufferStatus(GL.GL_FRAMEBUFFER)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        if status != GL.GL_FRAMEBUFFER_COMPLETE:
            try:
                GL.glDeleteFramebuffers(1, [fbo])
                GL.glDeleteTextures([tex])
            except Exception:
                pass
            raise RuntimeError("framebuffer status {}".format(status))
        return (fbo, tex)

    def output_texture(self, out):
        return out[1]

    def delete_output(self, out):
        if out is None:
            return
        self.GL.glDeleteFramebuffers(1, [out[0]])
        self.GL.glDeleteTextures([out[1]])

    def begin_output(self, out, coord_w, coord_h, pix_w, pix_h, n_eyes):
        GL = self.GL
        self._cur = (out, pix_w, pix_h)
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, out[0])
        GL.glViewport(0, 0, pix_w * n_eyes, pix_h)
        GL.glDisable(GL.GL_BLEND)
        GL.glDisable(GL.GL_DEPTH_TEST)
        GL.glClearColor(0.0, 0.0, 0.0, 0.0)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT)
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        if self.FLIP_Y:
            GL.glOrtho(0, coord_w, coord_h, 0, -1, 1)     # 上から数える px。メモリの1行目が絵の下 (素材と同じ並び)
        else:
            GL.glOrtho(0, coord_w, 0, coord_h, -1, 1)
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

    def set_eye(self, i):
        _, pw, ph = self._cur
        self._eye = i
        self.GL.glViewport(i * pw, 0, pw, ph)

    def draw_textured(self, tex, x0, y0, x1, y1, clip=None):
        GL = self.GL
        _, pw, ph = self._cur
        if clip is not None:
            cx0, cy0, cx1, cy1 = clip
            if cx1 <= cx0 or cy1 <= cy0:
                return
            gy = (ph - cy1) if self.FLIP_Y else cy0
            GL.glEnable(GL.GL_SCISSOR_TEST)
            GL.glScissor(self._eye * pw + cx0, gy, cx1 - cx0, cy1 - cy0)
        vt, vb = (1.0, 0.0) if self.FLIP_Y else (0.0, 1.0)     # 絵の上端/下端のテクスチャ座標
        GL.glEnable(GL.GL_TEXTURE_2D)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexEnvi(GL.GL_TEXTURE_ENV, GL.GL_TEXTURE_ENV_MODE, GL.GL_REPLACE)
        GL.glBegin(GL.GL_QUADS)
        GL.glTexCoord2f(0.0, vt)
        GL.glVertex2f(x0, y0)
        GL.glTexCoord2f(1.0, vt)
        GL.glVertex2f(x1, y0)
        GL.glTexCoord2f(1.0, vb)
        GL.glVertex2f(x1, y1)
        GL.glTexCoord2f(0.0, vb)
        GL.glVertex2f(x0, y1)
        GL.glEnd()
        GL.glDisable(GL.GL_TEXTURE_2D)
        if clip is not None:
            GL.glDisable(GL.GL_SCISSOR_TEST)

    def fill_rect(self, color, x0, y0, x1, y1):
        GL = self.GL
        c = [v / 255.0 for v in color]
        GL.glColor4f(c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0)
        GL.glBegin(GL.GL_QUADS)
        GL.glVertex2f(x0, y0)
        GL.glVertex2f(x1, y0)
        GL.glVertex2f(x1, y1)
        GL.glVertex2f(x0, y1)
        GL.glEnd()
        GL.glColor4f(1.0, 1.0, 1.0, 1.0)

    def end_output(self, out):
        GL = self.GL
        GL.glBindFramebuffer(GL.GL_FRAMEBUFFER, 0)
        self._cur = None
        # 出力テクスチャにもミップマップを付ける (SteamVR が縮小して表示するときに荒れにくくする)
        if int(HUD_MIPMAP_MAX_LEVEL) > 0:
            self.gen_mipmap(out[1])

    def fence(self):
        if not self._fence_ok:
            return None
        GL = self.GL
        try:
            f = GL.glFenceSync(GL.GL_SYNC_GPU_COMMANDS_COMPLETE, 0)
            GL.glFlush()
            return f or None
        except Exception:
            self._fence_ok = False
            return None

    def fence_done(self, token):
        GL = self.GL
        try:
            r = int(GL.glClientWaitSync(token, 0, 0))
            return r in (GL.GL_ALREADY_SIGNALED, GL.GL_CONDITION_SATISFIED, GL.GL_WAIT_FAILED)
        except Exception:
            return True

    def fence_delete(self, token):
        try:
            self.GL.glDeleteSync(token)
        except Exception:
            pass

    def finish(self):
        self.GL.glFinish()

    def drain_errors(self):
        codes = []
        for _ in range(8):
            try:
                c = self.GL.glGetError()
            except Exception:
                break
            if not c:
                break
            codes.append(int(c))
        return codes

    def submit(self, fn_texture, handle, texture_struct):
        return fn_texture(handle, self.ctx.ct.byref(texture_struct))


def _hud_make_gfx():
    """
    HUD_GFX_BACKEND の描画の裏方を作る。今は 'opengl' だけ (D3D11 を足すときはここに分岐を足す)。
    D3D11 を作るときのメモ (他の LLM 向け):
      - 目的: ゲームが GPU を使い切っていても HUD の描画が順番待ちしないよう、GPU の優先度を上げる
        (IDXGIDevice::SetGPUThreadPriority。OpenGL からは使えない)。効くかは実機で統計の「GPU 待ち」を見て確かめる。
      - SteamVR へは Texture_t.eType = TextureType_DirectX, handle = ID3D11Texture2D* (ctypes / comtypes で呼ぶ)。
      - 上下の並び: D3D は左上原点なので upload で反転しない。draw_textured/fill_rect は板の px (左上原点) のまま使える。
      - フェンス: ID3D11Query (D3D11_QUERY_EVENT) を End して Flush、GetData(DONOTFLUSH) で終わったか見る。
      - ミップマップ: GenerateMips (D3D11_RESOURCE_MISC_GENERATE_MIPS + RENDER_TARGET)。切り抜きは RSSetScissorRects。
      - 描く仕組み: 頂点4つの四角 + テクスチャ1枚のシェーダー (混ぜずに上書き) と、単色の四角のシェーダー。
      - 確かめ方: テストキットの g1 (出力 = 素材) / g3 の絵が OpenGL 版と1ピクセルも違わないこと。
    """
    name = str(HUD_GFX_BACKEND).lower()
    if name != 'opengl':
        print("[HUD Warning] HUD_GFX_BACKEND '{}' はまだありません -> 'opengl'".format(HUD_GFX_BACKEND))
    return HudGfxOpenGL()


class HudPlateOverlay(object):
    """
    1枚板のHUD (OpenGL 動的テクスチャ + SteamVR オーバーレイ1枚)。
    描画は2段階:
      1) 素材テクスチャ (tex_src, 板と同じ px): 部品(層)を PIL で合成し、変わった範囲だけ書き込む。
      2) 出力テクスチャ (tex_out, FBO): tex_src を「奥行きの写し方」(拡大・ずらし) で描き直し、
         デバッグ用の縦線を足す。SteamVR に渡すのはこちら。解像度は HUD_TEXTURE_SCALE 倍。
    板(オーバーレイ)の位置は動かさない。視差は 2) の描き直しだけで作る (他のオーバーレイに隠れない)。
    FBO が使えない環境では 1) をそのまま渡す (奥行き・解像度変更・縦線なし)。
    """
    MODES = ('fakefar', 'far', 'plate')     # 見せ方 (F キーはこの順に切り替える)
    PREMULTIPLY_ALPHA = False   # 透明部分の縁が暗い/明るい場合は True を試す

    def __init__(self, debug=False, head_getter=None, eye_getter=None):
        self.vroverlay = None
        self.debug = debug
        self.initialized = False
        self.x, self.y, self.z = (float(v) for v in HUD_PLATE_POS)
        self.ss = hud_ss()
        self.mpp_base = float(HUD_METERS_PER_PIXEL) / self.ss      # 内部の絵の 1px の実寸
        self.mpp = self.mpp_base * float(HUD_SCALE)       # 1px の実寸 (拡大縮小込み)
        # オーバーレイは役割ごとに分け、1つのオーバーレイには常に同じテクスチャだけを渡す
        # (途中で大きさの違うテクスチャに替えると、SteamVR が受け取るときに GL エラーになるため)
        self._h_frame = None            # 'plate' の HUD (板の位置。出力テクスチャ)
        self._h_edge = None             # 'far' のとき: 板の位置の縦線だけ (縦線テクスチャ)
        self._h_far = None              # 'far' のとき: 遠くに置く HUD (出力テクスチャ)
        self._h_main = None             # いま出力テクスチャを渡す先 (_h_far か _h_frame)
        self._gl_err_reported = False
        self._tex_edge = None           # 'far' のとき: 板の位置に出す縦線だけのテクスチャ
        self._gfx = None                # 描画の裏方 (HudGfx)。GPU はこれだけを通して使う
        self._tex = None
        self._tex_out = None
        self._fbo = None
        self._visible = True
        self._last_apply_time = 0.0
        self._last_debug_time = 0.0
        self._apply_count = 0
        self._error_count = 0
        self._min_interval = 1.0 / max(10.0, float(HUD_MAX_FPS))
        self._values = {}
        self._thread = None
        self._lock = threading.Lock()
        self._pending = None
        self._pending_force = False
        self._sync_frame = None         # 最後に見たゲームのフレーム (HUD_GAME_SYNC)
        self._pend = deque()            # 予約: (渡す時刻, 写し方, 気づいた時刻, 待つ vsync の数)
        self._shown_key = None          # いま画面に出ている (はずの) ゲームのフレームの写し方
        self._shown_dir = None          # 'hybrid': いま画面に出ているゲームのフレームの目の位置 (見える方向に使う)
        self._t_pose = None             # 頭の位置を読んだ時刻 (display)
        self._t_submitted = 0.0
        self._t_finish = 0.0
        self._lat_ema = None            # 頭の位置を読んでから渡し終わるまで (なめらかにした値)
        self._shift_ref = None          # HUD_LATE_SHIFT: 今見えている絵を作った目 (両目の真ん中)
        self._shift_ref_next = None     # 描いたがまだ渡していない絵の目
        self._shift_now = None          # 今ずらしている量 (dx, dy) [m]。None = ずらしていない
        self._shift_t = None            # 最後にずらしを更新した時刻
        self._comp_watch = None         # _HudCompositorWatch (統計を出している間だけ使う)
        self._shift_pend = deque()      # ずらしの基準の待ち行列 (SteamVR へのコピーと vsync を待っている絵)
        self._next_tick = 0.0
        self._game_dt = None            # ゲームの1フレームの時間 (なめらかにした値)
        self._last_detect = None
        self._stats_sec = float(HUD_STATS_SEC)
        self._stats_reset(time.time())
        self._mode_req = False          # F キー: 'far' と 'plate' の切り替えの予約 (描画スレッドで行う)
        self._row_img = {}
        self._bar_cache = {}
        self._log_wrap = {}             # ログの通し番号 -> 折り返した (行, 色) のリスト
        self._log_art = {}              # (行, 色) -> にじみ付きの絵
        self._splash_t0 = None          # 起動時の表示を始めた時刻 (最初の描画のとき)。show_splash() で出し直す
        self._map_key = None            # 前回 FBO に描いたときの写し方

        rows = list(HUD_NOTICE_ROWS)
        self.rows = hud_normalize_notice_rows(rows)
        self._eye_auto = HUD_DEPTH_EYE_OFFSET is None
        self.depth = HudDepth(HUD_DEPTH_ENABLED, HUD_DEPTH_DISTANCE_M, HUD_DEPTH_KEEP_SIZE, self._default_eye_offset(),
                              HUD_DEPTH_CLAMP_NEAR, HUD_DEPTH_PREDICT_SEC, head_getter, eye_getter, HUD_STEREO_IPD_M)
        self.stereo = bool(HUD_STEREO) and self.depth.enabled
        mode = str(HUD_DEPTH_MODE)
        if mode not in self.MODES:
            print("[HUD Warning] HUD_DEPTH_MODE '{}' は使えません -> 'fakefar'".format(mode))
            mode = 'fakefar'
        if mode != 'plate' and not (self.depth.enabled and self.depth.distance > 0):
            mode = 'plate'
        self.mode = mode
        self.far = mode != 'plate'          # 'far' と 'fakefar' は同じ仕組み (オーバーレイを置く距離だけが違う)
        self.assets = HudAssets()
        ss = self.ss
        self.layout = HudLayout(self.assets, self.rows, self.mpp_base,
                                size_mult={'indicator': ss, 'notice': ss, 'text': ss, 'log': ss},
                                extra_margin_x=self._stereo_margin_px())
        self.board = HudNoticeBoard(self.rows)
        self.plate_w = self.layout.plate_w
        self.plate_h = self.layout.plate_h
        ts = self._output_scale()
        self.out_w = max(8, int(round(self.plate_w * ts)))
        self.out_h = max(8, int(round(self.plate_h * ts)))
        self._src_dirty = True          # 素材テクスチャが変わった (ミップマップを作り直す)
        self._layers = self._make_layers()
        self._init_overlay()
        if self.initialized:
            self.update_hud_state(force=True)
            if HUD_THREADED:
                try:
                    self._start_thread()
                except Exception as e:
                    print("[HUD Warning] 専用スレッドを始められません ({}) -> 操縦の処理の中で描きます".format(e))
                    self._thread = None
                    self._gfx.make_current()

    def _output_scale(self):
        """
        出力テクスチャ / 内部の絵 の倍率。
        自動 (HUD_TEXTURE_SCALE = None) のときは、基準の目から見た板の幅がヘッドセットの画面で何 px になるかを計算し、
        その HUD_TEXTURE_OVERSAMPLE 倍にする。必要以上に大きいと SteamVR が縮小するときに荒れ、小さいとぼやける。
        """
        if HUD_TEXTURE_SCALE is not None:
            return _hud_clamp(float(HUD_TEXTURE_SCALE) / self.ss, 0.05, 2.0)
        try:
            vrsys = _hud_vrsystem()
            rw = vrsys.getRecommendedRenderTargetSize()[0]
            l, r, tp, bt = vrsys.getProjectionRaw(openvr.Eye_Left)
            px_per_tan = rw / float(abs(r - l))                    # 画面の中心付近で、tan 1 あたりの画素
            ez = max(0.2, self.depth.eye_offset[2])
            need = self.plate_w * self.mpp / ez * px_per_tan * float(HUD_TEXTURE_OVERSAMPLE)
            scale = _hud_clamp(need / float(self.plate_w), 0.1, 1.0)
            print("[HUD Info] texture auto: headset {}px/tan, plate {:.0f}px on screen -> x{:.2f}".format(
                int(px_per_tan), need / float(HUD_TEXTURE_OVERSAMPLE), scale))
            return scale
        except Exception as e:
            print("[HUD Warning] テクスチャの解像度を自動で決められません ({}) -> 1.0 相当".format(e))
            return 1.0 / self.ss

    def _default_eye_offset(self):
        """基準の目の位置 (HUD 基準点から)。HUD_DEPTH_EYE_OFFSET = None ならシート座標の原点。"""
        if HUD_DEPTH_EYE_OFFSET is None:
            return (-self.x, -self.y, -self.z)
        return tuple(float(v) for v in HUD_DEPTH_EYE_OFFSET)

    def _stereo_margin_px(self):
        """立体視で左右の目の絵が横へずれる量 [px] (窓をこの分だけ横に広げる)。"""
        if not self.stereo:
            return 0
        ipd = HUD_STEREO_IPD_M if HUD_STEREO_IPD_M else 0.068
        ez0 = max(self.depth.eye_offset[2], 0.05)
        d = max(0.0, float(HUD_DEPTH_DISTANCE_M))
        return int(math.ceil(ipd / 2.0 * d / (ez0 + d) / self.mpp))

    def _make_layers(self):
        lay = self.layout
        layers = [_HudLayer('indicator', lay.ind.size, lay.ind.base)]
        for t in lay.texts:
            layers.append(_HudLayer('text', t.size, t.base, static_img=t.img))
        for i, g in enumerate(lay.row_geo):
            layers.append(_HudLayer('row', g.size, g.base, index=i))
        if lay.version is not None:
            layers.append(_HudLayer('text', lay.version.size, lay.version.base, static_img=lay.version.img))
        for i, lg in enumerate(lay.logs):                 # 0 = 普通, 1 = 大きく (どちらか1つだけ出す)
            layers.append(_HudLayer('log', lg.size, lg.base, index=i))
        if lay.splash is not None:
            layers.append(_HudLayer('splash', lay.splash.size, lay.splash.base, static_img=lay.splash.img))
        return layers

    # ---------------------------------------------------------------- OpenGL / OpenVR の準備
    def _init_fbo(self):
        """出力 (描き込み先) を作る。失敗したら self._fbo = None のまま (素材テクスチャを直接渡す)。"""
        gfx = self._gfx
        try:
            out = gfx.new_output(self.out_w * self._n_eyes(), self.out_h)
            self._outs = [out]
            if HUD_OUTPUT_DOUBLE_BUFFER:
                # 2枚目 (同じ大きさ)。交互に描いて渡す
                try:
                    self._outs.append(gfx.new_output(self.out_w * self._n_eyes(), self.out_h))
                except Exception as e2:
                    print("[HUD Warning] 2枚目の出力テクスチャを作れません ({}) -> 1枚で続けます".format(e2))
            self._out_i = 0
            self._fbo = self._outs[0]                       # 「出力がある」印 (中身はバックエンドの値)
            self._tex_out = gfx.output_texture(self._fbo)
        except Exception as e:
            print("[HUD Warning] FBO が使えません ({}: {}) -> 奥行き表示・解像度変更・縦線なしで続けます".format(
                type(e).__name__, e))
            self._fbo = None
            self._tex_out = None
            self._outs = []
            self.depth.enabled = False
            self.stereo = False      # 出力テクスチャがないので、立体視も 'far' も使えない
            self.far = False
            self.mode = 'plate'
            try:      # 素材テクスチャを直接渡すので、ミップマップなしの設定に戻す
                gfx.set_mipmap(self._tex, False)
            except Exception:
                pass

    def _init_overlay(self):
        try:
            self._gfx = _hud_make_gfx()
            # 縮小したときのやわらかさ (ミップマップの段を少し粗い側へ寄せる)
            self._tex = self._gfx.new_texture(self.plate_w, self.plate_h, mipmap=True,
                                              lod_bias=max(0.0, float(HUD_SOFTNESS)))
            # 中身が未初期化のままにならないよう、まず全面を透明で埋める
            self._upload_region(Image.new('RGBA', (self.plate_w, self.plate_h), (0, 0, 0, 0)), 0, 0)
            self._init_fbo()

            self.vroverlay = openvr.IVROverlay()
            self._fn_transform = self.vroverlay.function_table.setOverlayTransformAbsolute
            self._fn_texture = self.vroverlay.function_table.setOverlayTexture
            self._tex_struct = openvr.Texture_t()
            self._tex_struct.handle = int(self._tex_out if self._fbo is not None else self._tex)
            self._tex_struct.eType = self._gfx.texture_type
            self._tex_struct.eColorSpace = openvr.ColorSpace_Auto

            result, h = self.vroverlay.createOverlay(b'steam_vr_joystick_hud_plate', b'HUD plate')
            if result != 0:
                raise RuntimeError("createOverlay(plate) failed with code {}".format(result))
            self._h_frame = h
            self._setup_hud_overlay(h, int(HUD_OVERLAY_SORT_ORDER))
            self._place()
            if self.far:
                self._init_far()
                self._h_main = self._h_far
            else:
                self._h_main = self._h_frame
            self._show_for_mode()

            self.initialized = True
            atexit.register(self.close)
            print("[HUD Info] HUD plate ready: {}x{}px (texture {}x{}{}), {} notice row(s), {} text item(s), depth {}".format(
                self.plate_w, self.plate_h, self.out_w if self._fbo else self.plate_w,
                self.out_h if self._fbo else self.plate_h, ' x2 stereo' if self.stereo else '',
                len(self.rows), len(self.layout.texts),
                '{:.2f}m {}'.format(self.depth.distance, self.mode if self.far else
                                    ('plate keep-size' if self.depth.keep_size else 'plate'))
                if self.depth.is_active() else 'off'))
            print("[HUD Info] 見せ方: " + self._mode_text() + "  (コンソールの F キーで切り替え)")
        except Exception as e:
            print("[HUD Error] HUD plate init failed ({}: {}) -> HUD は表示されません".format(type(e).__name__, e))
            self.close()
            self.initialized = False

    def plate_center(self):
        """板(窓)の中心の位置 [m]。"""
        wc = self.layout.window_center
        return (self.x + wc[0] * self.mpp, self.y - wc[1] * self.mpp, self.z)

    def get_mode(self):
        """今の見せ方 ('fakefar' / 'far' / 'plate')。"""
        return self.mode

    def set_mode(self, mode):
        """
        見せ方を切り替える ('fakefar' / 'far' / 'plate')。実際の切り替えは次の描画のとき (描画スレッドで行う)。
        後でコントローラーの設定画面などから呼ぶ想定。切り替えられないときは False を返す。
        """
        if mode not in self.MODES:
            print("[HUD] 見せ方 '{}' はありません ({})".format(mode, ' / '.join(self.MODES)))
            return False
        if not self.initialized:
            return False
        if mode != 'plate' and (self._fbo is None or not self.depth.enabled or self.depth.distance <= 0):
            print("[HUD] この設定では '{}' に切り替えられません (奥行き表示が無効か、出力テクスチャがない)".format(mode))
            return False
        self._mode_req = mode
        if self._thread is None:
            self.update_hud_state(force=True)
        return True

    def cycle_mode(self):
        """次の見せ方へ (fakefar → far → plate → fakefar ...)。コンソールの F キー。"""
        i = self.MODES.index(self.mode) if self.mode in self.MODES else -1
        return self.set_mode(self.MODES[(i + 1) % len(self.MODES)])

    def toggle_far(self):
        """(古い名前) cycle_mode と同じ。"""
        return self.cycle_mode()

    def _mode_text(self):
        names = {'fakefar': "'fakefar' (通常: 板の {:.2f}m 奥に置いて 20m 先に見せる)",
                 'far': "'far' (最高の見え方: 本当に {:.0f}m 奥に置く" + ("、窓で切り抜く)" if HUD_FAR_WINDOW_CLIP else "、頭の位置は使わない)"),
                 'plate': "'plate' (互換: 板の上で描き直す)"}
        if self.mode == 'fakefar':
            s = names['fakefar'].format(self._far_dist())
        elif self.mode == 'far':
            s = names['far'].format(self._far_dist())
        else:
            return names['plate']
        return s + " 揺れ: plate の約 {:.0f}%".format(100.0 * self._far_wobble_ratio())

    def _switch_mode(self):
        """
        描画スレッドの中で呼ぶ。'far' と 'fakefar' は同じオーバーレイを置き直すだけ、'plate' とは表示するオーバーレイを
        入れ替えるだけ (どのオーバーレイにも、いつも同じテクスチャを渡す)。
        """
        mode, self._mode_req = self._mode_req, False
        if not mode or mode == self.mode:
            return
        self.mode = mode
        self.far = mode != 'plate'
        if self.far:
            if self._h_far is None:
                self._init_far()
            self._place()              # 'far' と 'fakefar' で置く距離が違う
        self._h_main = self._h_far if self.far else self._h_frame
        self._show_for_mode()
        self._map_key = None
        print("[HUD] 見せ方: " + self._mode_text())
        print("[HUD] 描き方: {}".format(self._draw_mode_text()))
        self._next_tick = 0.0

    def _set_sort_order(self, handle, order):
        """
        描画順の番号を設定する。SteamVR は「番号の小さい順」に描き、番号が同じものだけ遠い順に描く。
        なので番号を大きくすれば、遠くに置いた HUD でも他のオーバーレイより上に描かれる。
        """
        try:
            err = self.vroverlay.setOverlaySortOrder(handle, order)
            if err:
                print("[HUD Warning] setOverlaySortOrder({}) error {}".format(order, err))
            got = self.vroverlay.getOverlaySortOrder(handle)
            got = got[-1] if isinstance(got, tuple) else got
            print("[HUD Info] overlay sort order = {}".format(got))
        except Exception as e:
            print("[HUD Warning] 描画順を設定できません: {}: {}".format(type(e).__name__, e))

    def _place(self):
        """板 (と 'far' の遠いオーバーレイ) をシート座標の決まった位置に置く。頭の動きでは動かさない。"""
        self._place_one(self._h_frame, self.plate_center(), self.plate_w * self.mpp)
        if self._h_edge is not None:
            self._place_one(self._h_edge, self.plate_center(), self.plate_w * self.mpp)
        if self._h_far is not None:
            fc, k = self._far_geom()
            self._place_one(self._h_far, fc, self.plate_w * self.mpp * k)

    def _place_one(self, handle, center, width):
        m = openvr.HmdMatrix34_t()
        m.m[0][0] = m.m[1][1] = m.m[2][2] = 1.0
        m.m[0][3], m.m[1][3], m.m[2][3] = center
        self.vroverlay.setOverlayWidthInMeters(handle, width)
        self._fn_transform(handle, openvr.TrackingUniverseSeated, openvr.byref(m))

    # ---------------------------------------------------------------- 'far' (本当に遠くに置く)
    def _far_dist(self):
        """'far' のオーバーレイを置く距離 (板から奥へ) [m]。HUD の奥行きより遠くはしない。"""
        d = self.depth.distance
        if self.mode == 'fakefar':
            d = min(d, max(0.05, float(HUD_FAKEFAR_DIST_M)))
        return d

    def _far_geom(self):
        """
        'far' のオーバーレイの中心 [m] と、板に対する拡大率 k を返す。
        基準の目 E0 から見て、板とぴったり重なる大きさ・位置に、板の _far_dist() 奥へ置く。
        """
        eo = self.depth.eye_offset
        e0 = (self.x + eo[0], self.y + eo[1], self.z + eo[2])
        ez0 = max(eo[2], HudDepth.NEAR_LIMIT)
        dist = self._far_dist()
        k = (ez0 + dist) / ez0
        pc = self.plate_center()
        return (e0[0] + (pc[0] - e0[0]) * k, e0[1] + (pc[1] - e0[1]) * k, self.z - dist), k

    def _far_map(self, eye, eye_dir=None):
        """
        'far' のオーバーレイが HUD の虚像 (板の HUD_DEPTH_DISTANCE_M 奥) より手前にあるとき、
        目 eye から虚像がオーバーレイの上のどこに見えるかを、絵の写し方 (左, 上, 右, 下) [px] で返す。
        オーバーレイが虚像と同じ距離なら (0, 0, W, H) のまま (描き直し不要 = 揺れない)。
        虚像は空間に固定 (前後に動いたときの大きさの補正はしない。20m 先ならほぼ変わらない)。
        eye_dir を渡すと 'hybrid': 見える方向は eye_dir (ゲームの画面の頭の位置) から、描く場所は eye (最新の頭の位置) から。
            O = E + (V - Eg) * t,  t = (E.z - オーバーレイの z) / (Eg.z - 虚像の z)
        """
        W, H = float(self.plate_w), float(self.plate_h)
        dist = self._far_dist()
        if dist >= self.depth.distance - 1e-9 and eye_dir is None:
            return (0.0, 0.0, W, H)
        eo = self.depth.eye_offset
        e0 = (self.x + eo[0], self.y + eo[1], self.z + eo[2])
        ez0 = max(eo[2], HudDepth.NEAR_LIMIT)
        fc, k = self._far_geom()
        big_d = ez0 + self.depth.distance                 # 基準の目 → 虚像
        z_virtual = e0[2] - big_d
        ex, ey, ez = eye
        gx, gy, gz = eye_dir if eye_dir is not None else eye
        if ez - fc[2] < HudDepth.NEAR_LIMIT or gz - z_virtual < HudDepth.NEAR_LIMIT:
            return None
        f = (ez - fc[2]) / (gz - z_virtual)                # 虚像 → オーバーレイ への縮め方
        s = f * big_d / (ez0 + dist)
        ox = ex - f * gx + f * e0[0] - s * e0[0]
        oy = ey - f * gy + f * e0[1] - s * e0[1]
        mppf = self.mpp * k
        dx = ((s - 1.0) * fc[0] + ox) / mppf
        dy = -((s - 1.0) * fc[1] + oy) / mppf
        w2, h2 = W / 2.0, H / 2.0
        return (w2 - s * w2 + dx, h2 - s * h2 + dy, w2 + s * w2 + dx, h2 + s * h2 + dy)

    def _far_wobble_ratio(self):
        """'far' の揺れの大きさ (頭の位置の予測がずれたとき、板の方式を 1.0 とした割合)。"""
        ez0 = max(self.depth.eye_offset[2], HudDepth.NEAR_LIMIT)
        v = ez0 + self.depth.distance
        lo = ez0 + self._far_dist()
        return ((1.0 - lo / v) / lo) / ((1.0 - ez0 / v) / ez0)

    def _setup_hud_overlay(self, h, order):
        """HUD (出力テクスチャ) を受け取るオーバーレイの共通設定。"""
        vo = self.vroverlay
        vo.setOverlayColor(h, 1.0, 1.0, 1.0)
        vo.setOverlayAlpha(h, 1.0)
        if self.stereo:
            # テクスチャの左半分を左目、右半分を右目に表示させる
            vo.setOverlayFlag(h, openvr.VROverlayFlags_SideBySide_Parallel, True)
            if HUD_STEREO_TEXEL_ASPECT:
                vo.setOverlayTexelAspect(h, float(HUD_STEREO_TEXEL_ASPECT))
        self._set_sort_order(h, order)

    def _show_for_mode(self):
        """今の見せ方で使うオーバーレイだけ表示する。"""
        vo = self.vroverlay
        show = [self._h_far, self._h_edge] if self.far else [self._h_frame]
        for h in (self._h_frame, self._h_edge, self._h_far):
            if h is None:
                continue
            if h in show and self._visible:
                vo.showOverlay(h)
            else:
                vo.hideOverlay(h)

    def _init_far(self):
        """遠いオーバーレイと、板の位置に出す縦線だけのオーバーレイを用意する (1回だけ)。"""
        if self._h_far is not None:
            return
        result, h = self.vroverlay.createOverlay(b'steam_vr_joystick_hud_far', b'HUD far')
        if result != 0:
            raise RuntimeError("createOverlay(far) failed with code {}".format(result))
        self._h_far = h
        self._setup_hud_overlay(h, int(HUD_OVERLAY_SORT_ORDER) + 1)
        self._place()
        # 板の位置: デバッグ用の縦線だけ (動かないので1回描けばよい)
        e = int(round(float(HUD_DEBUG_EDGE_PX)))
        if e <= 0:
            return
        bw, bh = max(16, int(self.plate_w / self.ss)), max(16, int(self.plate_h / self.ss))
        img = Image.new('RGBA', (bw, bh), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, e - 1, bh - 1], fill=tuple(HUD_DEBUG_EDGE_COLOR))
        d.rectangle([bw - e, 0, bw - 1, bh - 1], fill=tuple(HUD_DEBUG_EDGE_COLOR))
        if HUD_DEBUG_EDGE_INNER_COLOR:
            e2 = max(1, e // 2)
            d.rectangle([e, 0, e + e2 - 1, bh - 1], fill=tuple(HUD_DEBUG_EDGE_INNER_COLOR))
            d.rectangle([bw - e - e2, 0, bw - e - 1, bh - 1], fill=tuple(HUD_DEBUG_EDGE_INNER_COLOR))
        gfx = self._gfx
        self._tex_edge = gfx.new_texture(bw, bh)
        gfx.upload(self._tex_edge, img, 0, 0, bh)
        gfx.finish()
        ts = openvr.Texture_t()
        ts.handle = int(self._tex_edge)
        ts.eType = gfx.texture_type
        ts.eColorSpace = openvr.ColorSpace_Auto
        self._edge_struct = ts
        result, he = self.vroverlay.createOverlay(b'steam_vr_joystick_hud_edge', b'HUD edge')
        if result != 0:
            print("[HUD Warning] 縦線のオーバーレイを作れません (code {})".format(result))
            return
        self._h_edge = he
        self.vroverlay.setOverlayColor(he, 1.0, 1.0, 1.0)
        self.vroverlay.setOverlayAlpha(he, 1.0)
        self._set_sort_order(he, int(HUD_OVERLAY_SORT_ORDER))
        self._place()
        err = self._gfx.submit(self._fn_texture, he, ts)
        self._clear_gl_errors('縦線')
        if err != 0:
            print("[HUD Warning] 縦線のテクスチャを渡せません (error {})".format(err))

    def _far_clip(self, eye):
        """
        目 eye から板(窓)を通して見える範囲を、遠いオーバーレイの上の px の四角 (左, 上, 右, 下) で返す。
        目が板を越えていれば None。SACC のステンシル (ガラスの形で切り抜く) の代わり。
        """
        ex, ey, ez = eye
        pc = self.plate_center()
        if ez - pc[2] < HudDepth.NEAR_LIMIT:
            return None
        fc, k = self._far_geom()
        t = (ez - fc[2]) / (ez - pc[2])                     # 目 → 板 の線を、遠い面まで延ばす倍率
        hw, hh = self.plate_w * self.mpp / 2.0, self.plate_h * self.mpp / 2.0
        mppf = self.mpp * k

        def far_px(px, py):
            fx = ex + (px - ex) * t
            fy = ey + (py - ey) * t
            return (fx - (fc[0] - hw * k)) / mppf, ((fc[1] + hh * k) - fy) / mppf
        x0, y0 = far_px(pc[0] - hw, pc[1] + hh)
        x1, y1 = far_px(pc[0] + hw, pc[1] - hh)
        return (x0, y0, x1, y1)

    def set_position(self, x=None, y=None, z=None):
        """基準点(板の位置)を動かす。部品は全部いっしょに動く。"""
        if x is not None:
            self.x = float(x)
        if y is not None:
            self.y = float(y)
        if z is not None:
            self.z = float(z)
        if self._eye_auto:
            self.depth.eye_offset = self._default_eye_offset()     # 基準の目はシート座標の原点のまま
        if self.initialized:
            try:
                self._place()
                self._map_key = None
            except Exception as e:
                print("[HUD Error] set_position failed: {}".format(e))

    # ---------------------------------------------------------------- 奥行きの操作
    def recenter_depth(self):
        """
        今の頭の位置を基準の目の位置にする (このセッションだけ)。
        ずっと使うなら、表示された値を [CONFIG] HUD_DEPTH_EYE_OFFSET に書く。
        """
        off = self.depth.offset_from((self.x, self.y, self.z))
        if off is None:
            print("[HUD] 頭の位置がまだ取れていません")
            return
        self.depth.eye_offset = off
        self._map_key = None
        if self.far:
            self._place()          # 遠いオーバーレイを新しい基準の目に合わせて置き直す
        print("[HUD] 基準の目の位置を変更: HUD_DEPTH_EYE_OFFSET = ({:.3f}, {:.3f}, {:.3f})  (固定するなら [CONFIG] に記入)".format(*off))

    def set_depth_distance(self, meters):
        """HUD の奥行き [m] を実行中に変える。"""
        self.depth.set_distance(meters)
        self._map_key = None

    # ---------------------------------------------------------------- 素材テクスチャ (PIL → tex_src)
    def _prep(self, img):
        """素材の画像を渡す前の下ごしらえ (バックエンドによらない部分だけ。上下の並べ替えはバックエンド)。"""
        if self.PREMULTIPLY_ALPHA:
            from PIL import ImageChops
            r, g, b, a = img.split()
            img = Image.merge('RGBA', (ImageChops.multiply(r, a), ImageChops.multiply(g, a),
                                       ImageChops.multiply(b, a), a))
        return img

    def _upload_region(self, img, px, py):
        """素材テクスチャの (px, py) [左上, 上から数える] に img を書き込む。"""
        self._gfx.make_current()
        self._gfx.upload(self._tex, self._prep(img), px, py, self.plate_h)

    # ---------------------------------------------------------------- 出力テクスチャ (FBO)
    def _map_rect(self, mp):
        """写し方 (s, ox, oy)[m] を、板の px 座標での「素材を描く四角」(x0, y0, x1, y1) にする。"""
        s, ox, oy = mp
        cx, cy, _ = self.plate_center()
        w2, h2 = self.plate_w / 2.0, self.plate_h / 2.0
        dx = ((s - 1.0) * cx + ox) / self.mpp
        dy = -((s - 1.0) * cy + oy) / self.mpp
        return (w2 - s * w2 + dx, h2 - s * h2 + dy, w2 + s * w2 + dx, h2 + s * h2 + dy)

    def _n_eyes(self):
        return 2 if self.stereo else 1

    def _draw_output(self, maps):
        """
        素材テクスチャを、目ごとの写し方 maps[i] で出力テクスチャへ描く (+ デバッグ用の縦線)。
        立体視なら出力テクスチャの左半分 = 左目、右半分 = 右目。GPU は self._gfx (HudGfx) だけで使う。
        """
        gfx = self._gfx
        W, H = self.plate_w, self.plate_h
        gfx.make_current()
        if len(getattr(self, '_outs', ())) > 1:
            # ダブルバッファ: 今 SteamVR に渡しているのとは別の1枚に描く
            self._out_i = 1 - self._out_i
            self._fbo = self._outs[self._out_i]
            self._tex_out = gfx.output_texture(self._fbo)
            self._tex_struct.handle = int(self._tex_out)
        if self._src_dirty and int(HUD_MIPMAP_MAX_LEVEL) > 0:
            gfx.gen_mipmap(self._tex)          # 中身が変わったときだけ縮小用の絵を作り直す
            self._src_dirty = False
        gfx.begin_output(self._fbo, W, H, self.out_w, self.out_h, self._n_eyes())
        e = float(HUD_DEBUG_EDGE_PX) * self.ss
        for i, mp in enumerate(maps):
            gfx.set_eye(i)
            if mp is not None and mp[0] == 'far':
                # 'far': 写し方 (qx0..qy1) で描き、板(窓)から見える範囲 (x0..y1, 出力の px) の外は描かない
                _, x0, y0, x1, y1, qx0, qy0, qx1, qy1 = mp
                if x1 > x0 and y1 > y0:
                    gfx.draw_textured(self._tex, qx0, qy0, qx1, qy1, clip=(x0, y0, x1, y1))
                    if HUD_DEBUG_CROSSHAIR:
                        self._draw_crosshair(qx0, qy0, qx1, qy1)
                continue
            if mp is not None:
                x0, y0, x1, y1 = self._map_rect(mp)
                gfx.draw_textured(self._tex, x0, y0, x1, y1)
            if e > 0 and not self.far:
                # 外側: 太い暗い線 / そのすぐ内側: 半分の太さの明るめの線 (明るい背景でも暗い背景でも見える)
                gfx.fill_rect(HUD_DEBUG_EDGE_COLOR, 0.0, 0.0, e, float(H))
                gfx.fill_rect(HUD_DEBUG_EDGE_COLOR, W - e, 0.0, float(W), float(H))
                if HUD_DEBUG_EDGE_INNER_COLOR:
                    e2 = e / 2.0
                    gfx.fill_rect(HUD_DEBUG_EDGE_INNER_COLOR, e, 0.0, e + e2, float(H))
                    gfx.fill_rect(HUD_DEBUG_EDGE_INNER_COLOR, W - e - e2, 0.0, W - e, float(H))
        gfx.end_output(self._fbo)

    def _draw_crosshair(self, qx0, qy0, qx1, qy1):
        """
        0.1.13 検証用: 基準の目 E0 の真正面 (HUD の絵の上の点) に十字線を描く。絵と同じ写し方 (qx0..qy1) で置くので、
        HUD の記号と同じ 20m 先に見える。頭を動かしてもここが景色に対して止まって見えれば、位置合わせが合っている。
        """
        try:
            eo = self.depth.eye_offset
            wl, wt = self.layout.window[0], self.layout.window[1]
            if HUD_DEBUG_CROSSHAIR_AT == 'plate':
                u, v = -wl, -wt                             # HUD の基準点
            else:
                u = eo[0] / self.mpp - wl                   # 基準の目の真正面。素材テクスチャの px (左上から)
                v = -eo[1] / self.mpp - wt
            W, H = float(self.plate_w), float(self.plate_h)
            sx, sy = (qx1 - qx0) / W, (qy1 - qy0) / H
            cx, cy = qx0 + u * sx, qy0 + v * sy
            a = float(HUD_DEBUG_CROSSHAIR_PX) * self.ss * sx
            w = max(1.0, float(HUD_DEBUG_CROSSHAIR_WIDTH_PX) * self.ss * sx) / 2.0
            col = HUD_DEBUG_CROSSHAIR_COLOR
            self._gfx.fill_rect(col, cx - a, cy - w, cx + a, cy + w)
            self._gfx.fill_rect(col, cx - w, cy - a, cx + w, cy + a)
        except Exception:
            pass

    def _eye_maps(self, eyes_now=None, eyes_dir=None):
        """
        目ごとの写し方のタプル (丸めない = Python の倍精度のまま)。板を越えた目は前回の値のまま。
        eyes_now / eyes_dir を渡すと 'hybrid' ('fakefar' / 'far' のみ): 描く場所は eyes_now、見える方向は eyes_dir から。
        """
        n = self._n_eyes()
        ident = (1.0, 0.0, 0.0)
        if self.far:
            ident = ('far', 0, 0, self.out_w, self.out_h, 0.0, 0.0, float(self.plate_w), float(self.plate_h))  # 切り抜かない
            if self.mode == 'far' and not HUD_FAR_WINDOW_CLIP:
                return (ident,) * n          # 'far' は頭の位置を使わない (位置合わせは SteamVR、切り抜きもしない)
        if not self.depth.is_active():
            return (ident,) * n
        if eyes_now is not None:
            eyes = list(eyes_now)
            dirs = list(eyes_dir) if eyes_dir is not None else list(eyes_now)
        else:
            self.depth.update()
            eyes = self.depth.eye_positions(self.stereo)
            dirs = eyes
        if eyes is None:
            return (ident,) * n
        if self.stereo and HUD_STEREO_SWAP:
            eyes = eyes[::-1]
            dirs = dirs[::-1]
        prev = self._map_key if self._map_key is not None else (ident,) * n
        out = []
        if self.far:
            # 出力テクスチャの px に丸める (変わったときだけ描き直す)
            sx = self.out_w / float(self.plate_w)
            sy = self.out_h / float(self.plate_h)
            for i, eye in enumerate(eyes):
                c = self._far_clip(eye)
                q = self._far_map(eye, dirs[i] if eyes_now is not None else None)
                if c is None or q is None:
                    # 目が板を越えた (板を裏から見ている): SACC と同じく見えなくする。
                    # HUD_DEPTH_CLAMP_NEAR = True のときだけ、前の絵のまま止める
                    if HUD_DEPTH_CLAMP_NEAR and prev[i] and prev[i][0] == 'far':
                        out.append(prev[i])
                    else:
                        out.append(('far', 0, 0, 0, 0) + ident[5:])     # 切り抜きの幅 0 = 何も描かない
                    continue
                r = ('far',
                     int(round(_hud_clamp(c[0] * sx, 0, self.out_w))), int(round(_hud_clamp(c[1] * sy, 0, self.out_h))),
                     int(round(_hud_clamp(c[2] * sx, 0, self.out_w))), int(round(_hud_clamp(c[3] * sy, 0, self.out_h))),
                     float(q[0]), float(q[1]), float(q[2]), float(q[3]))
                out.append(r)
            return tuple(out)
        for i, eye in enumerate(eyes):
            mp = self.depth.mapping((self.x, self.y, self.z), eye)
            out.append(prev[i] if mp is None else (float(mp[0]), float(mp[1]), float(mp[2])))
        return tuple(out)

    # ---------------------------------------------------------------- ゲームの画面と同じ vsync に出す (HUD_GAME_SYNC)
    def _sync_active(self):
        return (self._thread is not None and bool(HUD_GAME_SYNC) and _HUD_POSE.source == 'game'
                and (str(HUD_POSE_SOURCE) == 'game' or (str(HUD_POSE_SOURCE) == 'hybrid' and not self.far)))

    def _sync_new_frame(self, key):
        """
        新しいゲームのフレームに気づいたら、「その頭の位置の写し方 key を、いつ SteamVR に渡すか」を予約する。
        眠って待つと、その間にゲームのフレームを見落とす (見落とすと FPS を低く見積もり、待ちがさらに伸びる悪循環になる)。
        なので予約だけして、描画スレッドは 2ms ごとの確認を続け、時刻が来たら描いて渡す (_sync_release)。
        """
        fr = _HUD_POSE.frames
        if fr == self._sync_frame:
            return
        self._sync_frame = fr
        t_det = _HUD_POSE.last_change
        if self._last_detect is not None:
            dt = t_det - self._last_detect
            if 0.003 < dt < 0.5:
                self._game_dt = dt if self._game_dt is None else self._game_dt * 0.8 + dt * 0.2
        self._last_detect = t_det
        hold, k = self._sync_hold(t_det)
        self._pend.append((hold, key, t_det, k))
        while len(self._pend) > 8:                                  # 念のため (たまりすぎたら古いものから捨てる)
            self._pend.popleft()

    def _sync_hold(self, t_det):
        """ゲームのフレーム (頭の位置を t_det に見つけた) が画面に出る直前の vsync の時刻と、そこまでの vsync の数。"""
        hold, k = 0.0, 0
        try:
            frame, _ = _hud_display_timing()
            r = _hud_vrsystem().getTimeSinceLastVsync()
            if not (isinstance(r, tuple) and r[0]):
                raise RuntimeError('no vsync')
            now = time.time()
            last_v = now - (float(r[1]) % frame)                    # 直前の vsync の時刻
            t0 = t_det - 0.5 * float(HUD_GAME_POSE_POLL_SEC)       # ゲームが頭の位置を受け取ったおおよその時刻

            def vsync_after(tm):
                return last_v + math.ceil((tm - last_v) / frame - 1e-6) * frame
            v1 = vsync_after(t0)                                    # 頭の位置を受け取った後の最初の vsync
            if HUD_GAME_SYNC_DELAY_VSYNC is not None:
                k = max(0, int(HUD_GAME_SYNC_DELAY_VSYNC))
            else:
                gdt = self._game_dt if self._game_dt else frame
                v_show = vsync_after(t0 + gdt - float(HUD_GAME_SYNC_RENDER_MARGIN_SEC))  # ゲームのフレームが出る vsync (見積もり)
                k = max(0, int(round((v_show - v1) / frame)))      # その直前の vsync = v1 から k 個目
            if k > 0:
                hold = v1 + (k - 1) * frame + float(HUD_GAME_SYNC_AFTER_VSYNC_SEC)
        except Exception:
            hold, k = 0.0, 0
        return hold, k

    def _sync_release(self):
        """予約の時刻が来たものを取り出す (いちばん新しいもの)。なければ None。"""
        now = time.time() + 0.0005
        due = None
        while self._pend and self._pend[0][0] <= now:
            due = self._pend.popleft()
        return due

    # ---------------------------------------------------------------- 'hybrid' (2つの頭の位置を組み合わせる)
    def _hybrid_on(self):
        """'hybrid' か 'display' で、vsync ごとに描く方式が使えるとき。"""
        return (self._thread is not None and str(HUD_POSE_SOURCE) in ('hybrid', 'display') and self.far
                and self.depth.is_active() and self._fbo is not None)

    def _display_predict_sec(self):
        """
        'display' で描き続けるときの先読み: 常に「今から一定時間先」(vsync に合わせない = 時間とともに途切れず動く)。
        それ以外は None (= vsync に合わせた自動の先読み)。
        """
        if not (self._display_on() and HUD_DISPLAY_CONTINUOUS):
            return None
        if HUD_DISPLAY_PREDICT_SEC is not None:
            base = float(HUD_DISPLAY_PREDICT_SEC)
        else:
            try:
                frame, photons = _hud_display_timing()
            except Exception:
                frame, photons = 1.0 / 90.0, 0.011
            base = 0.5 * frame + photons          # 描いてから光るまでの平均 (次に読まれるまで平均半フレーム + 光るまで)
            if HUD_DISPLAY_LATENCY_COMP and self._lat_ema and not self._late_shift_on():
                base += self._lat_ema              # 頭の位置を読んでから渡し終わるまでの実際の時間 (GPU 待ちなど)
        return max(0.0, min(0.1, base + float(HUD_DEPTH_PREDICT_EXTRA_SEC)))

    def _display_on(self):
        return str(HUD_POSE_SOURCE) == 'display'

    def _hybrid_poll(self):
        """ゲームの頭の位置を確かめ、新しいフレームなら「いつ画面に出るか」と一緒に予約する (描かない)。"""
        try:
            g = _HUD_POSE.read(None)
        except Exception:
            return
        if _HUD_POSE.source != 'game' or g is None:
            self._pend.clear()
            self._shown_dir = None                   # ゲームの姿勢がないときは、最新の頭の位置だけで描く
            return
        fr = _HUD_POSE.frames
        if fr == self._sync_frame:
            return
        self._sync_frame = fr
        t_det = _HUD_POSE.last_change
        if self._last_detect is not None:
            dt = t_det - self._last_detect
            if 0.003 < dt < 0.5:
                self._game_dt = dt if self._game_dt is None else self._game_dt * 0.8 + dt * 0.2
        self._last_detect = t_det
        hold, k = self._sync_hold(t_det) if HUD_GAME_SYNC else (0.0, 0)
        eyes_g = self.depth.eyes_from(g[0], g[1], self.stereo)
        self._pend.append((hold, eyes_g, t_det, k))
        while len(self._pend) > 8:
            self._pend.popleft()

    def _hybrid_next_tick(self):
        """
        次に描く時刻。'hybrid' = 次の vsync の HUD_RENDER_AFTER_VSYNC_SEC 後。
        'display' = 次の vsync の HUD_DISPLAY_RENDER_LEAD_SEC 前 (SteamVR が姿勢を読む直前。過ぎていたらその次)。
        """
        try:
            frame, _ = _hud_display_timing()
            r = _hud_vrsystem().getTimeSinceLastVsync()
            if isinstance(r, tuple) and r[0]:
                now = time.time()
                to_v = frame - float(r[1]) % frame
                if self._display_on():
                    tick = now + to_v - float(HUD_DISPLAY_RENDER_LEAD_SEC)
                    if tick < now + 0.0005:
                        tick += frame
                    return tick
                return now + to_v + float(HUD_RENDER_AFTER_VSYNC_SEC)
        except Exception:
            pass
        return time.time() + 1.0 / max(10.0, float(HUD_MAX_FPS))

    def _hybrid_maps(self):
        """
        'hybrid' の写し方: 最新の頭の位置 (予測) と、今画面に出ているゲームのフレームの頭の位置から。
        'display' の写し方: 最新の頭の位置 (予測) だけから ('far' と同じ見え方)。
        """
        if self._display_on():
            self._pend.clear()
            self._shown_dir = None
        due = self._sync_release()
        if due is not None:
            self._shown_dir = due[1]
            self._stats_record(due[2], due[3])
        if self._fixed_ref_on():
            # 0.1.13: 絵は基準の目 E0 から見た形 (毎回同じ写し方)。頭の動きは _late_shift_apply がすべて直す
            eyes_ref = self._fixed_ref_eyes()
            self._t_pose = time.time()
            self._shift_ref_next = self._mid(eyes_ref)
            return self._eye_maps(eyes_ref, eyes_ref)
        lf = self._pose_full_fresh()
        if lf is not None:
            # 0.1.11 'full': 別スレッドが計算した写し方を代入するだけ (OpenGL 側は計算しない)
            self._t_pose = lf[0]
            self._shift_ref_next = lf[2]
            return lf[1]
        try:
            lp = self._pose_from_thread()
            if lp is not None:
                p = lp[1]                                   # 0.1.9: 別スレッドの計算結果を代入するだけ
                self._t_pose = lp[0]
            else:
                p = _read_head_pose(self._display_predict_sec())
                self._t_pose = time.time()
        except Exception:
            p = None
        if p is None:
            return self._map_key if self._map_key is not None else self._eye_maps()
        self.depth.head = tuple(float(v) for v in p[0])
        self.depth.rot = p[1]
        self.depth._refresh_eyes()
        eyes_now = self.depth.eyes_from(self.depth.head, self.depth.rot, self.stereo)
        self._shift_ref_next = self._mid(eyes_now)     # この絵を作った目 (両目の真ん中)。渡したら _shift_ref になる
        return self._eye_maps(eyes_now, self._shown_dir or eyes_now)

    def _draw_mode_text(self):
        """今の描き方 (起動時・切り替え時にコンソールへ出す)。"""
        src = str(HUD_POSE_SOURCE)
        if self._hybrid_on():
            if src == 'display' and HUD_DISPLAY_CONTINUOUS:
                return "display (vsync を待たず {:.1f}ms ごとに、常に {:.1f}ms 先を予測して描いて渡し続ける{})".format(
                    1000.0 * float(HUD_DISPLAY_INTERVAL_SEC), 1000.0 * (self._display_predict_sec() or 0.0),
                    "、出力テクスチャ2枚を交互" if len(getattr(self, '_outs', ())) > 1 else "")
            if src == 'display':
                return "display (vsync ごとに、次の vsync の {:.1f}ms 前に最新の予測で描く)".format(
                    1000.0 * float(HUD_DISPLAY_RENDER_LEAD_SEC))
            return "hybrid (vsync ごとに描く。見える方向はゲームの画面の頭の位置から)"
        if src in ('game', 'hybrid'):
            return "game (ゲームのフレームごとに描く)"
        if src == 'display' and not self.far:
            return "predict ('plate' では display は使えないため、vsync ごとに予測で描く)"
        return "predict (vsync ごとに予測で描く)"

    def _sync_next_time(self):
        """次の予約の時刻 (描画スレッドがそこまでに起きるため)。"""
        return self._pend[0][0] if self._pend else None

    # ---------------------------------------------------------------- 統計 (描き直しが間に合っているか)
    def toggle_stats(self):
        """統計の表示を入/切 (コンソールの S キー)。"""
        self._stats_sec = 0.0 if self._stats_sec > 0 else 5.0
        self._stats_reset(time.time())
        print("[HUD] 統計の表示: {}".format("{:.0f} 秒ごと".format(self._stats_sec) if self._stats_sec > 0 else "切"))

    def _stats_reset(self, now):
        if getattr(self, '_comp_watch', None) is not None:
            self._comp_watch.reset()
        self._st = {'t0': now, 'submits': 0, 'frames0': _HUD_POSE.frames, 'drawn': 0, 'skipped': 0,
                    'lat_sum': 0.0, 'lat_max': 0.0, 'late': 0, 'last_frame': _HUD_POSE.frames,
                    'wait_sum': 0.0, 'k_sum': 0}

    def _stats_record(self, t_det, k):
        """同期のとき: 予約したゲームのフレームを渡したときに記録する。"""
        if self._stats_sec <= 0:
            return
        st = self._st
        if not self._hybrid_on():
            st['submits'] += 1
        st['drawn'] += 1
        now = time.time()
        lat = now - t_det
        st['lat_sum'] += lat
        st['lat_max'] = max(st['lat_max'], lat)
        st['k_sum'] += k
        st['wait_sum'] += lat
        fr = _HUD_POSE.frames
        self._stats_vsync_check(st)

    def _stats_vsync_check(self, st):
        try:
            frame, _ = _hud_display_timing()
            r = _hud_vrsystem().getTimeSinceLastVsync()
            if isinstance(r, tuple) and r[0]:
                rem = frame - (float(r[1]) % frame)              # 渡し終えたとき、次の vsync までの残り
                if rem < float(HUD_STATS_LATE_MARGIN_SEC):
                    st['late'] += 1
                st['rem_n'] = st.get('rem_n', 0) + 1
                st['rem_sum'] = st.get('rem_sum', 0.0) + rem
                st['rem_min'] = min(st.get('rem_min', 1.0), rem)
        except Exception:
            pass

    def _stats_on_submit(self, waited=0.0):
        """
        HUD を渡すたびに記録する。'game' のとき、新しいゲームのフレームについて
          ・気づいてから SteamVR に渡し終わるまでの時間
          ・渡した時点で、次の vsync まで HUD_STATS_LATE_MARGIN_SEC 未満だったか (SteamVR の合成に間に合わない恐れ)
          ・前に描いたフレームから、描かずに飛ばしたゲームのフレームがあるか
        """
        if self._stats_sec <= 0:
            return
        st = self._st
        st['submits'] += 1
        if _HUD_POSE.source != 'game':
            return
        fr = _HUD_POSE.frames
        if fr == st['last_frame']:
            return
        st['skipped'] += max(0, fr - st['last_frame'] - 1)
        st['last_frame'] = fr
        st['drawn'] += 1
        lat = time.time() - _HUD_POSE.last_change
        st['lat_sum'] += lat
        st['lat_max'] = max(st['lat_max'], lat)
        try:
            frame, _ = _hud_display_timing()
            r = _hud_vrsystem().getTimeSinceLastVsync()
            if isinstance(r, tuple) and r[0]:
                if frame - (float(r[1]) % frame) < float(HUD_STATS_LATE_MARGIN_SEC):
                    st['late'] += 1
        except Exception:
            pass

    def _stats_maybe_print(self):
        if self._stats_sec <= 0:
            return
        now = time.time()
        st = self._st
        dt = now - st['t0']
        if dt < self._stats_sec:
            return
        games = _HUD_POSE.frames - st['frames0']
        n = max(1, st['drawn'])
        if self._sync_active() or self._hybrid_on():
            st['skipped'] = max(0, games - st['drawn'])     # 予約したのに渡さずに次へ進んだフレーム
        if self._hybrid_on() and self._display_on() and HUD_DISPLAY_CONTINUOUS:
            dn = max(1, st.get('dl_n', 0))
            print("[HUD 統計] display (描き続ける) | HUD を渡した {:.1f}回/s ({:.1f}ms ごと) | 頭の位置を読んでから渡し終わるまで "
                  "平均 {:.1f}ms 最大 {:.1f}ms うち GPU 待ち 平均 {:.1f}ms | 先読み {:.1f}ms".format(
                      st['submits'] / dt, 1000.0 * dt / max(1, st['submits']),
                      1000.0 * st.get('dl_sum', 0.0) / dn, 1000.0 * st.get('dl_max', 0.0),
                      1000.0 * st.get('fin_sum', 0.0) / dn, 1000.0 * (self._display_predict_sec() or 0.0))
                  + (" | ずらし {:.0f}回/s 最大 {:.1f}mm 止まった最長 {:.1f}ms (切り替え: コピー + {} vsync 後, 待ち 平均 {:.1f}ms, 10ms 超 {} 回)".format(
                      st.get('sh_n', 0) / dt, 1000.0 * st.get('sh_max', 0.0), 1000.0 * st.get('sh_gap', 0.0),
                      int(HUD_LATE_SHIFT_SWITCH_VSYNC), 1000.0 * st.get('cw_sum', 0.0) / max(1, st.get('cw_n', 0)),
                      st.get('sh_gap10', 0))
                     if self._late_shift_on() else " | ずらし 切")
                  + (self._comp_watch.text(dt) if self._comp_watch is not None else ""))
            self._stats_reset(now)
            return
        if self._hybrid_on() and self._display_on():
            rn = max(1, st.get('rem_n', 0))
            print("[HUD 統計] display | HUD を渡した {:.1f}回/s (vsync ごとが目標) | 渡し終えたとき次の vsync まで "
                  "平均 {:.1f}ms 最小 {:.1f}ms (0 に近いほど間に合っていない恐れ)".format(
                      st['submits'] / dt, 1000.0 * st.get('rem_sum', 0.0) / rn, 1000.0 * st.get('rem_min', 0.0)))
            self._stats_reset(now)
            return
        if _HUD_POSE.source == 'game':
            if self._hybrid_on():
                print("[HUD 統計] hybrid | ゲーム {:.1f}fps | HUD を渡した {:.1f}回/s (vsync ごと) | ゲームのフレームが画面に出るまで "
                      "平均 {:.1f}ms | 待った vsync 平均 {:.2f} | 予約を使わず飛ばしたフレーム {}回 | ゲームの1フレーム {:.1f}ms".format(
                          games / dt, st['submits'] / dt, 1000.0 * st['lat_sum'] / n, float(st['k_sum']) / n,
                          st['skipped'], 1000.0 * (self._game_dt or 0.0)))
                self._stats_reset(now)
                return
            print("[HUD 統計] ゲーム {:.1f}fps | HUD を渡した {:.1f}回/s | ゲームのフレームに気づいてから渡し終わるまで "
                  "平均 {:.1f}ms 最大 {:.1f}ms | vsync 直前 (<{:.0f}ms) {}回 ({:.0f}%) | 描かずに飛ばしたフレーム {}回 | "
                  "同期: 待った vsync 平均 {:.2f} ゲームの1フレーム {:.1f}ms".format(
                      games / dt, st['submits'] / dt, 1000.0 * st['lat_sum'] / n, 1000.0 * st['lat_max'],
                      1000.0 * float(HUD_STATS_LATE_MARGIN_SEC), st['late'], 100.0 * st['late'] / n, st['skipped'],
                      float(st['k_sum']) / n, 1000.0 * (self._game_dt or 0.0)))
        else:
            print("[HUD 統計] 頭の位置は predict | HUD を渡した {:.1f}回/s".format(st['submits'] / dt))
        self._stats_reset(now)

    def _submit(self):
        t0 = time.time()
        self._gpu_wait()                           # GPU が描き終わるまで待つ (ゲームが GPU を使い切っていると長くなる)
        self._t_finish = time.time() - t0
        err = self._gfx.submit(self._fn_texture, self._h_main, self._tex_struct)
        self._t_submitted = time.time()
        if HUD_JITTER_CSV.on:
            ref = self._shift_ref_next
            HUD_JITTER_CSV.row('submit', gpu_wait_ms=self._t_finish * 1000.0,
                               pose_age_ms=(self._t_submitted - self._t_pose) * 1000.0 if self._t_pose else None,
                               ref_x_mm=ref[0] * 1000.0 if ref else None, ref_y_mm=ref[1] * 1000.0 if ref else None)
        if self._late_shift_on() and self._shift_ref_next is not None:
            self._shift_after_submit(self._shift_ref_next)
        self._clear_gl_errors('HUD')
        if err != 0:
            raise RuntimeError("SetOverlayTexture error {}".format(err))

    def _gpu_wait(self):
        """
        GPU が描き終わるまで待つ。HUD_LATE_SHIFT が効いているときは finish で止まらず、フェンスを約 1ms ごとに見ながら
        その間も遠いオーバーレイのずらしを更新する (GPU 待ちが長くても、位置合わせはゲームの負荷に引っ張られない)。
        フェンスが使えなければ finish。
        """
        gfx = self._gfx
        if self._late_shift_on():
            fence = gfx.fence()
            if fence is not None:
                try:
                    t_end = time.time() + 0.25
                    while not gfx.fence_done(fence):
                        if time.time() > t_end:
                            break
                        self._late_shift_update()
                        time.sleep(0.001)
                    else:
                        return
                finally:
                    gfx.fence_delete(fence)
        gfx.finish()

    def _shift_after_submit(self, ref):
        """
        渡した絵の目 ref を、ずらしの基準の「待ち行列」に入れる。HUD_LATE_SHIFT_WAIT_COPY なら、SteamVR へのコピー
        (こちらの GL に積まれる) の後ろにフェンスを置き、それが終わってさらに HUD_LATE_SHIFT_SWITCH_VSYNC 回 vsync が来るまで、
        前の絵の基準のまま (_shift_resolve が順番に切り替える)。
        待ちが次に渡すまでより長くても、前の分を無理に切り替えない (行列にして、渡した順に切り替える)。
        """
        fence = self._gfx.fence() if HUD_LATE_SHIFT_WAIT_COPY else None
        # [フェンス, 目, 渡した時刻, (コピー完了時の vsync 番号, 時刻) または None]
        self._shift_pend.append([fence, ref, time.time(), None if fence else (_hud_vsync_count(), time.time())])
        while len(self._shift_pend) > 6:
            self._shift_pop(self._shift_pend.popleft(), False)
        self._late_shift_update()

    def _shift_pop(self, pend, record):
        """待ち行列から出した1件で、ずらしの基準を切り替える。"""
        if pend[0] is not None:
            self._gfx.fence_delete(pend[0])
            pend[0] = None
        self._shift_ref = pend[1]
        if HUD_JITTER_CSV.on:
            HUD_JITTER_CSV.row('switch', since_submit_ms=(time.time() - pend[2]) * 1000.0,
                               ref_x_mm=pend[1][0] * 1000.0, ref_y_mm=pend[1][1] * 1000.0)
        if record and self._stats_sec > 0:
            st = self._st
            st['cw_n'] = st.get('cw_n', 0) + 1
            st['cw_sum'] = st.get('cw_sum', 0.0) + (time.time() - pend[2])

    def _shift_resolve(self, force=False):
        """待ち行列の先頭から、切り替えてよいもの (force なら全部) を順に切り替える。"""
        gfx = self._gfx
        try:
            frame = _hud_display_timing()[0]
        except Exception:
            frame = 1.0 / 90.0
        n = int(HUD_LATE_SHIFT_SWITCH_VSYNC)
        c = None
        while self._shift_pend:
            pend = self._shift_pend[0]
            now = time.time()
            if not force:
                if pend[0] is not None:
                    if not gfx.fence_done(pend[0]) and now - pend[2] <= 0.25:
                        return
                    gfx.fence_delete(pend[0])
                    pend[0] = None
                    pend[3] = (_hud_vsync_count(), now)          # コピー完了。ここから vsync を数える
                if n > 0:
                    if c is None:
                        c = _hud_vsync_count()
                    c0, t0 = pend[3]
                    done = (now - t0 > (n + 1) * frame              # vsync の番号が進まない環境でも止まらない
                            or (c is not None and c0 is not None and c - c0 >= n) or now - pend[2] > 0.25)
                    if not done:
                        return
            self._shift_pop(self._shift_pend.popleft(), not force)

    def _late_shift_on(self):
        """上下左右のずらし (HUD_LATE_SHIFT) を使うとき: 'display' で描き続けていて、遠いオーバーレイが板の奥にある。"""
        return (bool(HUD_LATE_SHIFT) and self._h_far is not None and self._h_main == self._h_far
                and self._display_on() and bool(HUD_DISPLAY_CONTINUOUS) and self._hybrid_on())

    def _fixed_ref_on(self):
        """HUD_FIXED_REF (0.1.13) を使うとき: 'fakefar' でずらしが効いている。"""
        return bool(HUD_FIXED_REF) and self._late_shift_on()

    def _fixed_ref_eyes(self):
        """基準の目 E0 (両目の真ん中) に、まっすぐ前を向いた頭があるとしたときの目の位置。"""
        eo = self.depth.eye_offset
        e0 = (self.x + eo[0], self.y + eo[1], self.z + eo[2])
        self.depth._refresh_eyes()
        return self.depth.eyes_from(e0, ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)), self.stereo)

    @staticmethod
    def _mid(eyes):
        n = float(len(eyes))
        return tuple(sum(e[i] for e in eyes) / n for i in range(3))

    def _late_shift_update(self):
        """
        遠いオーバーレイを、絵を作った目 _shift_ref と最新の予測の目 E の差だけ上下左右にずらす。
        虚像 V が見える場所 O = E + (V - E) * t,  t = (E.z - オーバーレイの z) / (E.z - 虚像の z)。
        目が横に d 動くと O は d * (1 - t) 動く (V によらず同じ = 平行移動で直せる)。
        'far' (虚像と同じ距離) では t = 1 なのでずらさない。前後の動き (拡大縮小) は直さない。
        """
        self._shift_resolve()
        if self._pose_full_fresh() is not None:
            return                                          # 0.1.11 'full': ずらしは別スレッドが計算して動かす
        ref = self._shift_ref
        if ref is None:
            return
        try:
            frame, photons = _hud_display_timing()
        except Exception:
            frame, photons = 1.0 / 90.0, 0.011
        lp = self._pose_from_thread()
        if lp is not None:
            p, lead = lp[2], lp[3]                          # 0.1.9: 別スレッドの計算結果を代入するだけ
        else:
            lead = self._shift_lead(frame, photons)
            try:
                p = _read_head_pose(lead)
            except Exception:
                p = None
        self._late_shift_apply(p, lead)

    def _late_shift_apply(self, p, lead):
        """姿勢 p (先読み lead で予測したもの) から、ずらし量を計算して遠いオーバーレイを動かす (描く側 / 'full' の別スレッドの両方から)。"""
        ref = self._shift_ref
        if p is None or ref is None:
            return
        e = self._mid(self.depth.eyes_from(tuple(float(v) for v in p[0]), p[1], self.stereo))
        fc, k = self._far_geom()
        eo = self.depth.eye_offset
        z_virtual = self.z + eo[2] - (max(eo[2], HudDepth.NEAR_LIMIT) + self.depth.distance)
        if e[2] - z_virtual < HudDepth.NEAR_LIMIT:
            return
        lim = float(HUD_LATE_SHIFT_MAX_M)
        if float(HUD_TEXTURE_FREEZE_HZ or 0.0) > 0.0:
            lim = max(lim, float(HUD_TEXTURE_FREEZE_SHIFT_MAX_M))   # 絵を絞っている間は絵が古いので、大きくずらす
        fz = fc[2]
        if self._fixed_ref_on():
            lim = max(lim, float(HUD_FIXED_REF_SHIFT_MAX_M))        # 0.1.13: 基準の目からの差を全部ずらすので大きめ
            if HUD_FIXED_REF_FOLLOW_Z:
                # 頭の前後の動きに合わせてオーバーレイも前後へ (目からの距離が変わらない = 見た目の大きさが変わらない)。
                # 虚像も同じだけ前後するとみなす (keep_size と同じ)。板より手前 (板の 2cm 奥まで) には出さない
                dz = _hud_clamp(e[2] - ref[2], -lim, min(lim, self.z - 0.02 - fc[2]))
                fz = fc[2] + dz
                z_virtual += dz
        r = 1.0 - (e[2] - fz) / (e[2] - z_virtual)
        dx = _hud_clamp((e[0] - ref[0]) * r, -lim, lim)
        dy = _hud_clamp((e[1] - ref[1]) * r, -lim, lim)
        m = openvr.HmdMatrix34_t()
        m.m[0][0] = m.m[1][1] = m.m[2][2] = 1.0
        m.m[0][3], m.m[1][3], m.m[2][3] = fc[0] + dx, fc[1] + dy, fz
        self._fn_transform(self._h_far, openvr.TrackingUniverseSeated, openvr.byref(m))
        self._shift_now = (dx, dy)
        if HUD_JITTER_CSV.on:
            HUD_JITTER_CSV.row('shift', eye_x_mm=e[0] * 1000.0, eye_y_mm=e[1] * 1000.0, ref_x_mm=ref[0] * 1000.0,
                               ref_y_mm=ref[1] * 1000.0, dx_mm=dx * 1000.0, dy_mm=dy * 1000.0, lead_ms=lead * 1000.0)
        now = time.time()
        gap = now - self._shift_t if self._shift_t else 0.0
        self._shift_t = now
        if self._stats_sec > 0:
            st = self._st
            if gap < 1.0:
                st['sh_gap'] = max(st.get('sh_gap', 0.0), gap)       # ずらしの更新が止まった最長の時間 (CPU が重いと伸びる)
                st['sh_gap10'] = st.get('sh_gap10', 0) + (1 if gap > 0.010 else 0)
            st['sh_n'] = st.get('sh_n', 0) + 1
            st['sh_max'] = max(st.get('sh_max', 0.0), math.sqrt(dx * dx + dy * dy))

    def _shift_lead(self, frame, photons):
        """
        ずらしの予測の先読み [秒]。HUD_LATE_SHIFT_VSYNC_TARGET なら「今書いた位置を SteamVR が使う画面が光る時刻」まで:
        次の vsync の HUD_LATE_SHIFT_RUNNING_START_SEC 前より前なら次の vsync、過ぎていればその次 (+ vsync から光るまで)。
        """
        lead = None
        if HUD_DISPLAY_PREDICT_SEC is not None:
            lead = float(HUD_DISPLAY_PREDICT_SEC)
        elif HUD_LATE_SHIFT_VSYNC_TARGET:
            try:
                r = _hud_vrsystem().getTimeSinceLastVsync()
                if isinstance(r, tuple) and r[0]:
                    to_v = frame - float(r[1]) % frame
                    if to_v < float(HUD_LATE_SHIFT_RUNNING_START_SEC):
                        to_v += frame
                    lead = to_v + photons
            except Exception:
                lead = None
        if lead is None:
            lead = 0.5 * frame + photons
        return max(0.0, min(0.1, lead + float(HUD_DEPTH_PREDICT_EXTRA_SEC)))

    def _late_shift_reset(self):
        """ずらしを使わなくなったら、遠いオーバーレイを元の位置に戻す。"""
        self._shift_resolve(force=True)
        self._shift_ref = None
        if self._shift_now is not None:
            self._shift_now = None
            if self._h_far is not None:
                fc, k = self._far_geom()
                self._place_one(self._h_far, fc, self.plate_w * self.mpp * k)

    def _clear_gl_errors(self, what):
        """
        SteamVR はテクスチャを受け取るとき、こちらの GL の環境で処理をする。そこで出た GL エラーが残っていると、
        次のこちらの GL 呼び出しのエラーに見えてしまうので、ここで取り除く (最初の1回だけ表示)。
        """
        codes = self._gfx.drain_errors()
        if codes and not self._gl_err_reported:
            self._gl_err_reported = True
            print("[HUD Warning] SteamVR が{}のテクスチャを受け取るときに GL エラー {} (表示は続けます)".format(what, codes))

    # ---------------------------------------------------------------- 部品(層)の絵
    def _render_indicator(self, key):
        bar_h, yaw_x, yaw_y, cross_x, cross_y, pov, yellow = key
        g = self.layout.ind
        img = Image.new('RGBA', g.size, (0, 0, 0, 0))
        if g.panel_img is not None:
            img.alpha_composite(g.panel_img, dest=g.panel_xy)
        p = g.glow_pad
        _hud_blit_ko(img, g.frame_g, (g.frame_xy[0] - p, g.frame_xy[1] - p))
        if bar_h > 0:
            _hud_blit_ko(img, self._bar_sprite(bar_h, yellow), (g.bar_x0 - p, g.bar_y1 - bar_h - p))
        if pov and g.pov_g is not None:
            _hud_blit_ko(img, g.pov_g, (g.pov_xy[0] - p, g.pov_xy[1] - p))
        _hud_blit_ko(img, g.yaw_g, (yaw_x - p, yaw_y - p))
        _hud_blit_ko(img, g.cross_g, (cross_x - p, cross_y - p))
        return img

    def _bar_sprite(self, bar_h, yellow):
        """スロットルバー (にじみ付き)。高さごとに作って使い回す。"""
        key = (bar_h, bool(yellow))
        img = self._bar_cache.get(key)
        if img is None:
            rgb = tuple(HUD_BAR_COLOR_YELLOW) if yellow else tuple(self.assets.bar_color)
            img = hud_glow(Image.new('RGBA', (self.layout.ind.bar_w, bar_h), rgb[:3] + (255,)))
            if len(self._bar_cache) > 1024:
                self._bar_cache.clear()
            self._bar_cache[key] = img
        return img

    def _render_row(self, index, color, texts=None):
        key = (index, color, texts)
        if key in self._row_img:
            return self._row_img[key]
        row = self.rows[index]
        geo = self.layout.row_geo[index]
        art = self.assets.row_art(row, color, self.layout.mult.get('notice', 1.0), texts)
        img = Image.new('RGBA', geo.size, (0, 0, 0, 0))
        if geo.margin > 0:
            img.alpha_composite(Image.new('RGBA', geo.size, self.layout.panel_rgba))
        # 段の大きさはレイアウト時 (確保した幅) に決めてある。絵はその真ん中に置く
        _hud_blit_ko(img, art, ((geo.size[0] - art.width) // 2, (geo.size[1] - art.height) // 2))
        if len(self._row_img) > 256:
            self._row_img.clear()
        self._row_img[key] = img
        return img

    # ---------------------------------------------------------------- デバッグログの層
    LOG_MODE_OF_LAYER = ('normal', 'large')

    def _log_lines_of(self, serial, text, idx):
        """1回分のログを折り返した [(行, 色), ...] (通し番号と大きさごとに覚える)。"""
        r = self._log_wrap.get((serial, idx))
        if r is not None:
            return r
        color = tuple(HUD_LOG_COLOR)
        for word, c in HUD_LOG_COLOR_RULES:
            if word in text:
                color = tuple(c)
                break
        g = self.layout.logs[idx]
        try:
            lines = self.assets.fonts.wrap_line(text, g.font_px, g.text_w, max(1, int(HUD_LOG_WRAP_MAX)))
        except Exception:
            lines = [text[:80]]
        r = [(ln, color) for ln in lines]
        if len(self._log_wrap) > 400:
            self._log_wrap.clear()
        self._log_wrap[(serial, idx)] = r
        return r

    def _log_key(self, now, idx=0):
        """
        ログの層 idx (0 = 普通, 1 = 大きく) にいま出す行 (上から順の ((行, 色), ...))。出さなければ None。
        HUD_LOG.mode と合う層だけが行を持つ。変わったときだけ描き直す。
        """
        if idx >= len(self.layout.logs) or HUD_LOG.mode != self.LOG_MODE_OF_LAYER[idx]:
            return None
        g = self.layout.logs[idx]
        rows = []
        for serial, text in HUD_LOG.recent(now, g.n_lines, float(HUD_LOG_HOLD_SEC or 0.0)):
            rows.extend(self._log_lines_of(serial, text, idx))
        rows = rows[-g.n_lines:]
        return tuple(rows) if rows else None

    def show_splash(self):
        """起動時の表示 (システム名とバージョン) をもう一度出す。"""
        self._splash_t0 = time.time()

    def _splash_key(self, now):
        """起動時の表示の濃さ (0～20 の段階)。None = 出さない。"""
        if self.layout.splash is None:
            return None
        if self._splash_t0 is None:
            self._splash_t0 = now
        left = float(HUD_SPLASH_SEC) - (now - self._splash_t0)
        if left <= 0.0:
            return None
        fade = max(0.0, float(HUD_SPLASH_FADE_SEC))
        a = 1.0 if (fade <= 0.0 or left >= fade) else left / fade
        step = int(math.ceil(a * 20))
        return step if step > 0 else None

    def _log_line_art(self, text, color, idx):
        key = (text, color, idx)
        img = self._log_art.get(key)
        if img is None:
            g = self.layout.logs[idx]
            img = self.assets.fonts.render_line(text, color, g.font_px, g.pitch)
            img = hud_glow(img, HUD_LOG_OPACITY) if HUD_LOG_GLOW else hud_fade(img, HUD_LOG_OPACITY)
            if len(self._log_art) > 256:
                self._log_art.clear()
            self._log_art[key] = img
        return img

    def _render_log(self, rows, idx=0):
        """ログの層の絵。行は下詰め (いちばん下 = いちばん新しい行)。"""
        g = self.layout.logs[idx]
        img = Image.new('RGBA', g.size, (0, 0, 0, 0))
        tx, ty = g.text_xy
        first = g.n_lines - len(rows)
        arts = [self._log_line_art(t, c, idx) for t, c in rows]
        pa = int(round(255 * _hud_clamp(HUD_LOG_PANEL_ALPHA, 0.0, 1.0)))
        if g.panel_m > 0 and pa > 0:
            # 行ごとの薄板 (重なっても濃くならないよう、形を1枚のマスクに描いてから敷く)
            mask = Image.new('L', g.size, 0)
            d = ImageDraw.Draw(mask)
            m = g.panel_m
            for i, a in enumerate(arts):
                w = min(g.text_w, a.width - 2 * g.glow_pad)
                y0 = ty + (first + i) * g.pitch
                d.rectangle([tx - m, y0 - m, tx + w + m - 1, y0 + g.pitch + m - 1], fill=pa)
            panel = Image.new('RGBA', g.size, tuple(HUD_PANEL_COLOR[:3]) + (0,))
            panel.putalpha(mask)
            img.alpha_composite(panel)
        for i, a in enumerate(arts):
            _hud_blit_ko(img, a, (tx - g.glow_pad, ty + (first + i) * g.pitch - g.glow_pad))
        return img

    def _indicator_key(self, throttle, pitch, roll, yaw, pov, yellow):
        g = self.layout.ind
        t = _hud_clamp(throttle, 0.0, 1.0)
        yaw = _hud_clamp(yaw, -1.0, 1.0) * HUD_YAW_SIGN
        roll = _hud_clamp(roll, -1.0, 1.0) * HUD_ROLL_SIGN
        pitch = _hud_clamp(pitch, -1.0, 1.0) * HUD_PITCH_SIGN
        return (int(round(g.bar_inner_h * t)),
                int(round(g.box_cx + yaw * g.travel_x - g.yaw.width / 2.0)),
                int(round(g.box_cy - g.yaw.height / 2.0)),
                int(round(g.box_cx + roll * g.travel_x - g.cross.width / 2.0)),
                int(round(g.box_cy - pitch * g.travel_y - g.cross.height / 2.0)),
                bool(pov), bool(yellow))

    def _refresh_layers(self, ind_key, board_key, log_key=None, splash_key=None):
        """変わった層だけ作り直し、書き換える範囲(四角)を返す。"""
        rects = []
        for L in self._layers:
            if L.kind == 'indicator':
                vis, key = True, ind_key
            elif L.kind == 'row':
                key = board_key[L.index]
                vis = key[0]
            elif L.kind == 'log':
                key = log_key[L.index] if log_key else None
                vis = key is not None
            elif L.kind == 'splash':
                vis, key = splash_key is not None, splash_key
            else:
                vis, key = True, None
            state = (vis, key)
            if state == L.state:
                continue
            if not vis:
                L.img = None
            elif L.kind == 'indicator':
                L.img = self._render_indicator(key)
            elif L.kind == 'row':
                L.img = self._render_row(L.index, key[1], key[2])
            elif L.kind == 'log':
                L.img = self._render_log(key, L.index)
            elif L.kind == 'splash':
                L.img = L.static_img if key >= 20 else hud_fade_by(L.static_img, key / 20.0)
            else:
                L.img = L.static_img
            if L.rect is not None:
                rects.append(L.rect)
            if vis and L.img is not None:
                L.rect = (L.base[0], L.base[1], L.base[0] + L.img.width, L.base[1] + L.img.height)
                rects.append(L.rect)
            else:
                L.rect = None
            L.state = state
        return rects

    def _recomposite(self, rects):
        """rects を覆う範囲だけ、全部の層から合成し直して素材テクスチャに書く。"""
        rx0 = max(0, min(r[0] for r in rects))
        ry0 = max(0, min(r[1] for r in rects))
        rx1 = min(self.plate_w, max(r[2] for r in rects))
        ry1 = min(self.plate_h, max(r[3] for r in rects))
        if rx1 <= rx0 or ry1 <= ry0:
            return False
        out = Image.new('RGBA', (rx1 - rx0, ry1 - ry0), (0, 0, 0, 0))
        for L in self._layers:
            if L.rect is None or L.img is None:
                continue
            lx0, ly0, lx1, ly1 = L.rect
            ix0, iy0, ix1, iy1 = max(lx0, rx0), max(ly0, ry0), min(lx1, rx1), min(ly1, ry1)
            if ix1 <= ix0 or iy1 <= iy0:
                continue
            out.alpha_composite(L.img.crop((ix0 - lx0, iy0 - ly0, ix1 - lx0, iy1 - ly0)),
                                dest=(ix0 - rx0, iy0 - ry0))
        self._upload_region(out, rx0, ry0)
        return True

    # ---------------------------------------------------------------- 毎フレーム
    def update_hud_state(self, throttle_val=0.0, pitch_val=0.0, roll_val=0.0, yaw_val=0.0,
                         bmark_pressed=False, cece27_toggle=False, pov_mode=False, force=False,
                         signals=None, buttons=None, values=None):
        """
        入力値と信号を受け取って HUD を更新する (Joystick.update() から毎フレーム呼ばれる)。
          signals : {'sig:...': bool} 追加の信号
          buttons : {vJoyボタン番号: bool}  → 'vbtn:番号' の信号になる
          values  : {'名前': 値} 通知の段の 'text_fn' に渡す値 (例 'cruise_power')
        専用スレッドで描いているときは、値を預けるだけですぐ戻る (描くのはスレッド側)。
        """
        if not self.initialized or not self._visible:
            return
        args = (throttle_val, pitch_val, roll_val, yaw_val, bmark_pressed, cece27_toggle, pov_mode,
                dict(signals) if signals else None, dict(buttons) if buttons else None,
                dict(values) if values else None)
        if self._thread is not None:
            with self._lock:
                self._pending = args
                self._pending_force = self._pending_force or force
            return
        self._apply(args, force)

    # ---------------------------------------------------------------- 専用スレッド
    def _start_thread(self):
        """GL の環境をこのスレッドから外し、描画専用のスレッドに渡す。"""
        self._gfx.detach()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._thread_main, name='hud_render')
        self._thread.daemon = True
        self._thread.start()
        self._pose_thread = threading.Thread(target=self._pose_thread_main, name='hud_pose')
        self._pose_thread.daemon = True
        self._pose_thread.start()

    def _pose_thread_main(self):
        """
        0.1.9 (検証用): HUD_POSE_THREAD の間、約 HUD_POSE_THREAD_INTERVAL_SEC ごとに頭の位置を2通りに予測して
        self._pose_latest = (計算した時刻, 絵用の姿勢, ずらし用の姿勢, ずらしの先読み) に入れる (タプルの代入なので途中の値は見えない)。
        絵用 = _display_predict_sec() 先、ずらし用 = _shift_lead() 先 (描く側で読むときと同じ先読み)。GL は使わない。
        """
        _hud_fine_timer()
        if HUD_THREAD_HIGH_PRIORITY:
            _hud_raise_thread_priority()
        err = 0
        while not self._stop.is_set():
            if not HUD_POSE_THREAD:
                self._pose_latest = None
                self._pose_full = None
                time.sleep(0.005)
                continue
            try:
                try:
                    frame, photons = _hud_display_timing()
                except Exception:
                    frame, photons = 1.0 / 90.0, 0.011
                p_tex = _read_head_pose(self._display_predict_sec())
                lead = self._shift_lead(frame, photons)
                p_shift = _read_head_pose(lead)
                if p_tex is not None and p_shift is not None:
                    self._pose_latest = (time.time(), p_tex, p_shift, lead)
                    if HUD_POSE_THREAD == 'full' and self._hybrid_on():
                        # 0.1.11 'full': 写し方 (視差・拡大縮小) とずらしもここで計算する。描く側はこの値を読むだけ
                        head = tuple(float(v) for v in p_tex[0])
                        self.depth.head, self.depth.rot = head, p_tex[1]
                        self.depth._refresh_eyes()
                        eyes_now = self.depth.eyes_from(head, p_tex[1], self.stereo)
                        maps = self._eye_maps(eyes_now, self._shown_dir or eyes_now)
                        self._pose_full = (time.time(), maps, self._mid(eyes_now))
                        if self._late_shift_on():
                            self._late_shift_apply(p_shift, lead)
                    else:
                        self._pose_full = None
            except Exception as e:
                err += 1
                if err <= 3:
                    print("[HUD Error] 頭の位置の別スレッド: {}: {}".format(type(e).__name__, e))
            time.sleep(max(0.0005, float(HUD_POSE_THREAD_INTERVAL_SEC)))

    def _pose_full_fresh(self):
        """0.1.11 'full' で、別スレッドの新しい計算結果 (時刻, 写し方, 絵を作った目) があればそれ、無ければ None。"""
        if HUD_POSE_THREAD != 'full':
            return None
        lf = getattr(self, '_pose_full', None)
        if lf is None or time.time() - lf[0] > float(HUD_POSE_THREAD_MAX_AGE_SEC):
            return None
        return lf

    def _pose_from_thread(self):
        """HUD_POSE_THREAD で、別スレッドの新しい計算結果があればそれ (タプル)、無ければ None (呼ぶ側がその場で読む)。"""
        if not HUD_POSE_THREAD:
            return None
        lp = getattr(self, '_pose_latest', None)
        if lp is None or time.time() - lp[0] > float(HUD_POSE_THREAD_MAX_AGE_SEC):
            return None
        return lp

    def _thread_main(self):
        _hud_fine_timer()
        if HUD_THREAD_HIGH_PRIORITY:
            _hud_raise_thread_priority()
        self._gfx.make_current()
        print("[HUD] 描き方: {}".format(self._draw_mode_text()))
        last = None
        while not self._stop.is_set():
            if self._hybrid_on():
                # 'hybrid': 2ms ごとにゲームの新しいフレームを確かめ (予約だけ)、vsync ごとに1回描く
                # 'display': ゲームは見ず、vsync ごとに SteamVR が画面を作る直前に1回描く
                now = time.time()
                if self._next_tick <= 0.0:
                    self._next_tick = self._hybrid_next_tick()
                if self._display_on() and HUD_DISPLAY_CONTINUOUS:
                    # 描き続ける: 間隔ごとに最新の予測で描いて渡す (SteamVR は画面を作る瞬間の最新の1枚を使う)
                    time.sleep(max(0.0005, float(HUD_DISPLAY_INTERVAL_SEC)))
                    if self._late_shift_on():
                        self._late_shift_update()          # 描く前にもずらしを最新に (コピー待ちの切り替えもここで見る)
                    if self._stats_sec > 0:
                        if self._comp_watch is None:
                            self._comp_watch = _HudCompositorWatch()
                        self._comp_watch.poll()            # SteamVR の合成自身が間に合っているか (統計)
                    self._next_tick = time.time()
                elif self._display_on():
                    time.sleep(max(0.0002, self._next_tick - now))
                else:
                    time.sleep(max(0.0005, min(float(HUD_GAME_POSE_POLL_SEC), self._next_tick - now)))
                    self._hybrid_poll()
                if time.time() < self._next_tick:
                    continue
                self._next_tick = self._hybrid_next_tick()
            elif _HUD_POSE.source == 'game':
                w = float(HUD_GAME_POSE_POLL_SEC)                          # ゲームの新しいフレームを待つ (姿勢が変われば描き直す)
                nxt = self._sync_next_time()
                if nxt is not None:
                    w = min(w, nxt - time.time())                          # 予約の時刻にも起きる
                time.sleep(max(0.0005, w))
            else:
                _hud_wait_next_frame()
            with self._lock:
                args, force = self._pending, self._pending_force
                self._pending_force = False
            if args is None:
                args = last
            if args is None:
                continue
            last = args
            if self._visible:
                self._apply(args, force)
        try:
            self._gfx.detach()
        except Exception:
            pass

    def _apply(self, args, force=False):
        """1回分の描画 (どちらのスレッドからでも同じ)。"""
        (throttle_val, pitch_val, roll_val, yaw_val, bmark_pressed, cece27_toggle, pov_mode,
         signals, buttons, values) = args
        now = time.time()
        if self._mode_req:
            try:
                self._switch_mode()
                force = True
            except Exception as e:
                print("[HUD Error] 見せ方を切り替えられません: {}: {}".format(type(e).__name__, e))

        sig = {'sig:always': True, 'sig:font_test': bool(HUD_FONT_TEST),
               'sig:left_app_menu': bool(bmark_pressed), 'sig:cece27': bool(cece27_toggle),
               'sig:pov_mode': bool(pov_mode)}
        if values:
            self._values.update(values)
        self._values.setdefault('throttle', throttle_val)
        if signals:
            sig.update(signals)
        if buttons:
            for n, s in buttons.items():
                sig['vbtn:{}'.format(n)] = bool(s)
        self.board.set_signals(sig)
        # 段ごとに (出ているか, 色, 'text_fn' の文字)
        board_key = tuple((vis, col, hud_row_texts(self.rows[i], self._values) if (vis and self.rows[i]['dynamic']) else None)
                          for i, (vis, col) in enumerate(self.board.update(now)))

        if self.debug and now - self._last_debug_time >= 1.0:
            self._last_debug_time = now
            print("[HUD Debug] thr={:.2f} pitch={:+.2f} roll={:+.2f} yaw={:+.2f} rows={} head={} map={} applies={}".format(
                throttle_val, pitch_val, roll_val, yaw_val, board_key, self.depth.head, self._map_key,
                self._apply_count))

        if self._thread is None and (not force) and (now - self._last_apply_time < self._min_interval):
            return

        try:
            ind_key = self._indicator_key(throttle_val, pitch_val, roll_val, yaw_val, pov_mode,
                                          self.board.is_any(HUD_BAR_YELLOW_WHEN))
            splash_key = self._splash_key(now)
            if splash_key is not None and HUD_SPLASH_HIDE_LOG:
                log_key = None
            else:
                log_key = [self._log_key(now, i) for i in range(len(self.layout.logs))]
            rects = self._refresh_layers(ind_key, board_key, log_key, splash_key)
            content_changed = bool(rects) and self._recomposite(rects)
            if content_changed:
                self._src_dirty = True
            if self._shift_now is not None and not self._late_shift_on():
                self._late_shift_reset()
            if self._fbo is None:
                if content_changed or force:
                    self._submit()
            elif self._hybrid_on():
                key = self._hybrid_maps()
                redraw = content_changed or force or key != self._map_key or getattr(self, '_freeze_pending', False)
                fz = float(HUD_TEXTURE_FREEZE_HZ or 0.0)
                if redraw and fz > 0.0 and not force and self._late_shift_on():
                    # JIT1: 絵の描き直しを fz 回/秒に絞る (ずらしは _late_shift_update がそのまま続ける)。
                    # 絞って描かなかった変更 (ログの行など) は _freeze_pending で覚えておき、次に描ける時に描く。
                    if now - getattr(self, '_t_freeze_draw', 0.0) < 1.0 / fz:
                        self._freeze_pending = True
                        redraw = False
                if redraw:
                    self._freeze_pending = False
                    self._t_freeze_draw = now
                    self._draw_output(key)
                    self._map_key = key
                    self._submit()
                    lat = self._t_submitted - self._t_pose if self._t_pose else 0.0
                    if 0.0 <= lat < 0.1:
                        self._lat_ema = lat if self._lat_ema is None else self._lat_ema * 0.9 + lat * 0.1
                    if self._stats_sec > 0:
                        st = self._st
                        st['submits'] += 1
                        st['dl_n'] = st.get('dl_n', 0) + 1
                        st['dl_sum'] = st.get('dl_sum', 0.0) + lat
                        st['dl_max'] = max(st.get('dl_max', 0.0), lat)
                        st['fin_sum'] = st.get('fin_sum', 0.0) + self._t_finish
                        if self._display_on():
                            self._stats_vsync_check(st)
            elif self._sync_active():
                # ゲームの画面と同じ vsync に出す: 新しいフレームの写し方は予約し、時刻が来たら描いて渡す
                key = self._eye_maps()
                self._sync_new_frame(key)
                due = self._sync_release()
                if due is not None:
                    self._shown_key = due[1]
                if self._shown_key is None:
                    self._shown_key = key
                if content_changed or force or due is not None or self._shown_key != self._map_key:
                    self._draw_output(self._shown_key)
                    self._map_key = self._shown_key
                    self._submit()
                    if due is not None:
                        self._stats_record(due[2], due[3])
                    else:
                        self._st['submits'] += 1 if self._stats_sec > 0 else 0
            else:
                key = self._eye_maps()
                self._pend.clear()
                self._shown_key = None
                if content_changed or force or key != self._map_key:
                    self._draw_output(key)
                    self._map_key = key
                    self._submit()
                    self._stats_on_submit()
            self._last_apply_time = now
            self._apply_count += 1
            self._stats_maybe_print()
        except Exception as e:
            for L in self._layers:
                L.state = None
            self._map_key = None
            self._error_count += 1
            if self._error_count <= 5 or self._error_count % 200 == 0:
                print("[HUD Error] update failed ({}x): {}: {}".format(
                    self._error_count, type(e).__name__, e))

    def show(self):
        if self.initialized:
            self._visible = True
            self._show_for_mode()

    def hide(self):
        if self.initialized:
            self._visible = False
            for h in (self._h_frame, self._h_edge, self._h_far):
                if h is not None:
                    self.vroverlay.hideOverlay(h)

    def close(self):
        th = getattr(self, '_thread', None)
        if th is not None:
            self._stop.set()
            th.join(1.0)
            self._thread = None
        pth = getattr(self, '_pose_thread', None)
        if pth is not None:
            pth.join(0.5)
            self._pose_thread = None
        try:
            for h in (self._h_frame, self._h_edge, self._h_far):
                if self.vroverlay is not None and h is not None:
                    try:
                        self.vroverlay.destroyOverlay(h)
                    except Exception:
                        pass
            self._h_frame = self._h_edge = self._h_far = self._h_main = None
            if self._gfx is not None:
                gfx = self._gfx
                try:
                    gfx.make_current()
                    for out in list(getattr(self, '_outs', ())):
                        gfx.delete_output(out)
                    for t in (self._tex, self._tex_edge):
                        if t is not None:
                            gfx.delete_texture(t)
                except Exception:
                    pass
                gfx.close()
                self._gfx = None
        finally:
            self.initialized = False


# ==============================================================================
# クォータニオン数学クラス
# ==============================================================================
class Quaternion:
    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w = float(w)
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    @classmethod
    def from_matrix(cls, m):
        tr = m[0][0] + m[1][1] + m[2][2]
        if tr > 0:
            S = math.sqrt(tr + 1.0) * 2.0
            qw = 0.25 * S
            qx = (m[2][1] - m[1][2]) / S
            qy = (m[0][2] - m[2][0]) / S
            qz = (m[1][0] - m[0][1]) / S
        elif (m[0][0] > m[1][1]) and (m[0][0] > m[2][2]):
            S = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2.0
            qw = (m[2][1] - m[1][2]) / S
            qx = 0.25 * S
            qy = (m[0][1] + m[1][0]) / S
            qz = (m[0][2] + m[2][0]) / S
        elif m[1][1] > m[2][2]:
            S = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2.0
            qw = (m[0][2] - m[2][0]) / S
            qx = (m[0][1] + m[1][0]) / S
            qy = 0.25 * S
            qz = (m[1][2] + m[2][1]) / S
        else:
            S = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2.0
            qw = (m[1][0] - m[0][1]) / S
            qx = (m[0][2] + m[2][0]) / S
            qy = (m[1][2] + m[2][1]) / S
            qz = 0.25 * S
        return cls(qw, qx, qy, qz)

    @classmethod
    def from_euler(cls, yaw_deg, roll_deg, pitch_deg):
        cy = math.cos(math.radians(yaw_deg * 0.5))
        sy = math.sin(math.radians(yaw_deg * 0.5))
        cr = math.cos(math.radians(roll_deg * 0.5))
        sr = math.sin(math.radians(roll_deg * 0.5))
        cp = math.cos(math.radians(pitch_deg * 0.5))
        sp = math.sin(math.radians(pitch_deg * 0.5))

        qw = cr * cp * cy + sr * sp * sy
        qx = sr * cp * cy - cr * sp * sy
        qy = cr * sp * cy + sr * cp * sy
        qz = cr * cp * sy - sr * sp * cy
        return cls(qw, qx, qy, qz)

    def conjugate(self):
        return Quaternion(self.w, -self.x, -self.y, -self.z)

    def multiply(self, q):
        w1, x1, y1, z1 = self.w, self.x, self.y, self.z
        w2, x2, y2, z2 = q.w, q.x, q.y, q.z
        return Quaternion(
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        )

    def to_axis_angles_deg(self):
        norm = math.sqrt(self.w*self.w + self.x*self.x + self.y*self.y + self.z*self.z)
        if norm == 0:
            return 0.0, 0.0, 0.0

        w = self.w / norm
        x = self.x / norm
        y = self.y / norm
        z = self.z / norm

        if w < 0:
            w = -w
            x = -x
            y = -y
            z = -z

        w = max(-1.0, min(1.0, w))
        angle_rad = 2.0 * math.acos(w)
        angle_deg = math.degrees(angle_rad)

        pitch_deg = angle_deg * x
        roll_deg = angle_deg * y
        yaw_deg = angle_deg * z

        return pitch_deg, roll_deg, yaw_deg

    def to_rotation_vector_deg(self):
        """回転ベクトル(単位軸 × 角度[度])を (x, y, z) で返す。
        ワールド座標: x=右(ピッチ軸) / y=上(ヨー軸) / z=手前(ロール軸)。
        ※ 旧 to_axis_angles_deg は (1) y を roll・z を yaw と呼んでいた (物理的には y=ヨー, z=ロール)、
           (2) 角度に「単位軸」ではなくクォータニオンの x,y,z (= 軸 × sin(θ/2)) を掛けていたため、
               出力が θ·sin(θ/2) ≒ θ²/2 になり、小さい角度でほとんど反応せず、
               他の軸の回転量にも出力が左右された (軸ずれ・感度ムラの原因)。
           ここでは (2) を直し、角度に比例した出力にしている。"""
        norm = math.sqrt(self.w*self.w + self.x*self.x + self.y*self.y + self.z*self.z)
        if norm == 0:
            return 0.0, 0.0, 0.0
        w, x, y, z = self.w / norm, self.x / norm, self.y / norm, self.z / norm
        if w < 0:
            w, x, y, z = -w, -x, -y, -z
        sin_half = math.sqrt(x*x + y*y + z*z)
        if sin_half < 1e-9:
            return 0.0, 0.0, 0.0
        angle_deg = math.degrees(2.0 * math.atan2(sin_half, w))
        if JOY_LEGACY_SCALING:
            return angle_deg * x, angle_deg * y, angle_deg * z
        k = angle_deg / sin_half
        return k * x, k * y, k * z


# ==============================================================================
# ユーティリティ関数
# ==============================================================================
def get_controller_quaternion(controller):
    try:
        matrix = None
        if hasattr(controller, 'pose') and controller.pose is not None:
            if hasattr(controller.pose, 'mDeviceToAbsoluteTracking'):
                matrix = controller.pose.mDeviceToAbsoluteTracking

        if matrix is not None:
            return Quaternion.from_matrix(matrix)
    except Exception:
        pass

    yaw = getattr(controller, 'yaw', 0.0)
    roll = getattr(controller, 'roll', 0.0)
    pitch = getattr(controller, 'pitch', 0.0)
    return Quaternion.from_euler(yaw, roll, pitch)


# ==============================================================================
# 左コントローラーの「手首ピボット補正」 (スロットルの中心ズレ対策)
# ==============================================================================
# コントローラーの原点は手首より前にあるため、手首を支点に縦回転(ピッチ)させると
# 原点が弧を描き、手は動かしていないのに z が変化してスロットルが動いてしまう。
# 「コントローラー原点 → 手首」のローカル座標オフセット o を使い、
#     手首位置 = 原点位置 + R * o        (R = コントローラーの回転行列)
# を入力にすれば、回転だけでは値が動かなくなる。
# o は機種・持ち方で変わるので、下の値を直接書くか、キャリブレーションで求める:
#     joystick.start_throttle_pivot_calibration()   # 左グリップは離したまま、手首を支点に
#     (約3秒、縦・横・ひねりを大きめに回す)          # 腕自体は動かさない
#     joystick.finish_throttle_pivot_calibration()  # 結果が表示され、そのまま適用される
THROTTLE_PIVOT_OFFSET = (0.0, -0.03, 0.0)   # (x, y, z) メートル。(0,0,0) = 補正なし

# SteamVR のレンダーモデル部品 (コントローラー原点からの各部品の位置) から
# 「握り(handgrip)の中心」を自動取得してオフセットに使う。None = 使わない。
# 優先順位: 計測結果ファイル > レンダーモデル部品 > 上の THROTTLE_PIVOT_OFFSET
THROTTLE_REF_COMPONENT = 'handgrip'
THROTTLE_PIVOT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'throttle_pivot.json')
# コンソールで C キー → 3秒後(振動1回)から5秒間計測 → 完了(振動2回)で保存・適用
PIVOT_CAL_DELAY_SEC = 3.0
PIVOT_CAL_RECORD_SEC = 5.0


def _device_index(ctr):
    i = ctr.id
    return int(i.value) if hasattr(i, 'value') else int(i)


def query_component_offset(ctr, comp_name):
    """SteamVR のレンダーモデルから、コントローラー原点→部品(comp_name)の位置(m)を得る。失敗時 None。"""
    try:
        vrsys = openvr.VRSystem()
        rm = openvr.VRRenderModels()
        idx = _device_index(ctr)
        model = vrsys.getStringTrackedDeviceProperty(idx, openvr.Prop_RenderModelName_String)
        # pyopenvr の版でシグネチャが違う:
        #   旧(同梱 1.0.0701): getComponentState(name, comp) -> (ok, controllerState, modeState, componentState)
        #   新(2.x)          : getComponentState(name, comp, controllerState, modeState) -> (ok, componentState)
        try:
            out = rm.getComponentState(model, comp_name)
        except TypeError:
            res = vrsys.getControllerState(idx)
            cstate = res[1] if isinstance(res, tuple) else res
            out = rm.getComponentState(model, comp_name, cstate, openvr.RenderModel_ControllerMode_State_t())
        if isinstance(out, tuple):
            ok, comp = out[0], out[-1]
        else:
            ok, comp = True, out
        if not ok:
            return None
        m = comp.mTrackingToComponentLocal.m
        o = (float(m[0][3]), float(m[1][3]), float(m[2][3]))
        if max(abs(v) for v in o) > 0.3 or max(abs(v) for v in o) < 1e-5:
            return None
        return o
    except Exception as e:
        print("[Throttle] レンダーモデル部品の取得に失敗: {}: {}".format(type(e).__name__, e))
        return None


class PivotCalibrator:
    """pose(回転R, 位置t) の列から、固定点(手首)に最も近づくローカルオフセット o を最小二乗で解く。
    R o - w = -t  (w = 手首の世界座標。未知) を 6 変数(o, w)として解く。"""

    def __init__(self):
        self.samples = []

    def add(self, m):
        R = [[m[i][j] for j in range(3)] for i in range(3)]
        t = [m[i][3] for i in range(3)]
        self.samples.append((R, t))

    def solve(self, ridge=1e-9):
        n = len(self.samples)
        if n < 30:
            return None, "サンプル不足 ({}件)".format(n)
        A = [[0.0] * 6 for _ in range(6)]
        B = [0.0] * 6
        for R, t in self.samples:
            for i in range(3):
                row = [R[i][0], R[i][1], R[i][2], 0.0, 0.0, 0.0]
                row[3 + i] = -1.0
                for a in range(6):
                    B[a] += row[a] * (-t[i])
                    for b in range(6):
                        A[a][b] += row[a] * row[b]
        for a in range(6):
            A[a][a] += ridge * n
        # ガウス消去
        M = [A[i][:] + [B[i]] for i in range(6)]
        for c in range(6):
            piv = max(range(c, 6), key=lambda r: abs(M[r][c]))
            if abs(M[piv][c]) < 1e-12:
                return None, "回転が足りません (特異)"
            M[c], M[piv] = M[piv], M[c]
            for r in range(c + 1, 6):
                f = M[r][c] / M[c][c]
                for k in range(c, 7):
                    M[r][k] -= f * M[c][k]
        x = [0.0] * 6
        for r in range(5, -1, -1):
            x[r] = (M[r][6] - sum(M[r][k] * x[k] for k in range(r + 1, 6))) / M[r][r]
        o = (x[0], x[1], x[2])
        if max(abs(v) for v in o) > 0.4:
            return None, "オフセットが大きすぎます {} (腕も動いた可能性)".format(tuple(round(v, 3) for v in o))
        return o, "ok"


# ==============================================================================
# スロットル制御クラス ( sensitivity 変数を追加 )
# ==============================================================================
class Throttle():

    def __init__(self, size=0.2, inverted=False, starting=0, sensitivity=1.0, enable_limiter=False):
        self.throttle_z = starting
        self.throttle_z_raw = starting 
        self.throttle_real_world_z = 0
        self.throttle_at_real_world_z = 0
        self.throttle_relative_zeroed = False
        self.throttle_grabbed = False
        self.invertion = -1 if inverted else 1
        self.size = size
        self.throttle_sensitivity = 1.4 # コンフィグ用感度設定変数
        self._last_delta = 0.0
        self.enable_limiter = enable_limiter  # スロットル専用リミッターを有効にするか
        self._limiter_bypassed = False        # リミッター超過後、緑に戻るまで自由操作にするフラグ

    @property
    def x(self):
        if self.size == 0:
            return 0
        val = self.throttle_z / self.size
        return max(0.0, min(1.0, val))

    def grabbed(self):
        self.throttle_grabbed = True

    def ungrabbed(self):
        self.throttle_grabbed = False

    def reset_to_center(self):
        self.throttle_z = self.size * 0.5
        self.throttle_relative_zeroed = False

    def update(self, value):
        if self.throttle_grabbed:
            val_inv = value * self.invertion
            if not self.throttle_relative_zeroed:
                self.throttle_real_world_z = val_inv
                self.throttle_at_real_world_z = self.throttle_z
                self.throttle_relative_zeroed = True
            else:
                # 【修正】差分 (delta) に対して感度を乗算する
                delta = (val_inv - self.throttle_real_world_z) * self.throttle_sensitivity
                new_z = self.throttle_at_real_world_z + delta

                # ==============================================================
                # 【アクセラレータ・リミッターシステム】 (スロットル専用)
                # ==============================================================
                target_limit = self.size * THROTTLE_ACCEL_LIMIT_RATIO
                if self.enable_limiter and THROTTLE_ACCELERATOR_LIMITTER and not CRUISE_MODE_ENABLED:
                    # スロットルが再び制限値以下（緑の領域）に戻ったらバイパスを解除
                    if self.throttle_z <= target_limit:
                        self._limiter_bypassed = False

                    if self._limiter_bypassed:
                        # すでにリミッターを超えており、まだ緑に戻っていない場合は自由に上下可能
                        self._last_delta = delta
                    else:
                        velocity = delta - self._last_delta
                        self._last_delta = delta

                        if new_z > target_limit:
                            if velocity < THROTTLE_ACCEL_THRESHOLD and self.throttle_z <= target_limit + 0.001:
                                new_z = target_limit
                            else:
                                # 勢いが足りているので、100%に飛ばさずアナログ操作のまま突破させる (緑に戻るまで自由)
                                self._limiter_bypassed = True
                else:
                    self._last_delta = delta

                self.throttle_z = new_z

                if self.throttle_z < 0:
                    self.throttle_z = 0
                elif self.throttle_z > self.size:
                    self.throttle_z = self.size
        else:
            self.throttle_relative_zeroed = False
            self._last_delta = 0.0


# ==============================================================================
# 仮想レバー（Virtual D-Pad）抽象化レイヤー
# ==============================================================================
class VirtualDPad:
    def __init__(self):
        self.enter_deadzone = 0.60
        self.exit_deadzone = 0.45
        self.disable_diagonal = False

        self.current_dir = 5
        self.last_dir = 5
        self.is_new_press = False

        self.pos_history = deque(maxlen=3)

        # Q29-3 調査用: 判定の中身 (動きは変えない。読むだけ)
        self.dbg_dist = 0.0          # 3 回平均の距離
        self.dbg_angle = 0.0         # 3 回平均の角度 [度] (atan2(y, x))
        self.dbg_threshold = self.enter_deadzone
        self.dbg_changes = 0         # 方向が変わった回数 (中立も1つの方向として数える)
        self.dbg_change_time = time.time()

    def _get_sector(self, angle_deg):
        if -22.5 <= angle_deg < 22.5:
            return 6
        elif 22.5 <= angle_deg < 67.5:
            return 9
        elif 67.5 <= angle_deg < 112.5:
            return 8
        elif 112.5 <= angle_deg < 157.5:
            return 7
        elif angle_deg >= 157.5 or angle_deg < -157.5:
            return 4
        elif -157.5 <= angle_deg < -112.5:
            return 1
        elif -112.5 <= angle_deg < -67.5:
            return 2
        elif -67.5 <= angle_deg < -22.5:
            return 3
        return 5

    def update(self, rx, ry):
        self.pos_history.append((rx, ry))
        avg_rx = sum(p[0] for p in self.pos_history) / len(self.pos_history)
        avg_ry = sum(p[1] for p in self.pos_history) / len(self.pos_history)

        distance = math.sqrt(avg_rx * avg_rx + avg_ry * avg_ry)
        self.dbg_dist = distance
        self.dbg_angle = math.degrees(math.atan2(avg_ry, avg_rx))
        self.dbg_threshold = self.enter_deadzone if self.current_dir == 5 else self.exit_deadzone

        if self.current_dir == 5:
            target_dir = 5 if distance < self.enter_deadzone else self._get_sector(math.degrees(math.atan2(avg_ry, avg_rx)))
        else:
            target_dir = 5 if distance < self.exit_deadzone else self._get_sector(math.degrees(math.atan2(avg_ry, avg_rx)))

        if self.disable_diagonal and target_dir in (7, 9, 1, 3):
            target_dir = 5

        self.is_new_press = (target_dir != 5) and (self.current_dir == 5)
        if target_dir != self.current_dir:
            now = time.time()
            self.dbg_changes += 1
            if DPAD_DEBUG_LOG:
                print("[DPAD] {} -> {}  R {:.2f} A {:+.1f} TH {:.2f} {}ms".format(
                    _DPAD_DIR_NAMES.get(self.current_dir, '?'), _DPAD_DIR_NAMES.get(target_dir, '?'),
                    distance, self.dbg_angle, self.dbg_threshold, int((now - self.dbg_change_time) * 1000)))
            self.dbg_change_time = now
        self.last_dir = self.current_dir
        self.current_dir = target_dir
        return self.current_dir


# ==============================================================================
# メイン Joystick クラス
# ==============================================================================
class Joystick(RightTrackpadAxisDisablerMixin, LeftTrackpadAxisDisablerMixin, VirtualPad):
    def __init__(self):
        print("=== {} ===".format(app_version_text()))
        self.amplification = 1
        super().__init__()
        self.x = 0
        self.y = 0
        self._vbtn_state = {}          # vJoy ボタン番号 -> 押されているか (通知インジゲータ用)
        self.cruise_center = False     # センタークルーズ中か (クルーズモード実装時に使う。HUD は 'C' と表示)
        self._hook_vjoy_buttons()

        # Throttle に感度 (sensitivity) を設定可能 (例: 1.0 = 標準感度)
        # メインスロットル(throttle_z)のみリミッターを有効化 (enable_limiter=True)
        self.throttle_z = Throttle(size=0.3, inverted=True, sensitivity=1.0, enable_limiter=True)
        self.throttle_y = Throttle(size=0.2, sensitivity=1.0, enable_limiter=False)
        self.throttle_x = Throttle(size=90, sensitivity=1.0, enable_limiter=False)

        self.grabbable_x = Throttle(size=1, starting=0.5)
        self.grabbable_y = Throttle(size=1, starting=0.5)
        self.grabbable_z = Throttle(size=1, starting=0.5)

        self._joystick_grabbed = False
        self.grab_base_q = None

        self.max_angle_range = 60
        # 軸ごとの最大角度[度]。小さいほど敏感。ラダー(yaw)が敏感なら max_angle_yaw を大きくする
        self.max_angle_pitch = self.max_angle_range
        self.max_angle_roll = self.max_angle_range
        self.max_angle_yaw = self.max_angle_range
        self.grab_heading = 0.0
        self._log_fp = None

        self.povytouchtoggle = False
        self.joysticknotouchpov = False
        self.left_app_menu_pressed = False

        self.left_touchpad_touched = False
        self.right_touchpad_touched = False
        self.left_touched_buttons = set()
        self.right_touched_buttons = set()

        self.left_touch_mask = 0
        self.right_touch_mask = 0

        self.pov_touch_ids = [32]

        self.dpad = VirtualDPad()
        self.pov_buttons = [19, 20, 21, 22]
        self.dpad_debug_hud = bool(DPAD_DEBUG_HUD)   # Q29-3 調査用
        self._dpad_dbg_out = '-'                     # 最後に vJoy に出したもの (POV の角度 / ボタン番号)
        self._dpad_dbg_vals = {}
        self._dpad_dbg_time = 0.0

        self.enable_oneshot_mode = False

        self._hud_axes = (0.5, 0.5, 0.5)
        self.is_cece27_active = False
        self.is_pov_mode = False          # 十字キーモード中か (HUDの十字アイコン表示用)
        self.throttle_pivot_offset = THROTTLE_PIVOT_OFFSET
        self._pivot_source = 'constant'
        self._pivot_cal = None
        self._cal_phase = None        # None / 'wait' / 'record'
        self._cal_t = 0.0
        self._component_tried = False
        self._load_pivot_file()
        print("[Throttle] Cキー(コンソール)で手首ピボット計測 (3秒後に開始/振動1回→5秒回す→振動2回で完了)")
        self.hud_swap_yaw_roll = HUD_SWAP_YAW_ROLL

        # --- HUD 初期化 --- (位置・大きさは [CONFIG] HUD_PLATE_POS ほか。失敗しても操作は続けられる)
        self.hud = HudPlateOverlay(debug=False)
        if not self.hud.initialized:
            self.hud = None

    def _hook_vjoy_buttons(self):
        """vJoy へ出すボタンの状態を見張り、HUD の通知 ('vbtn:番号') に使えるようにする。"""
        try:
            dev = self.device
            orig = dev.set_button
            state = self._vbtn_state

            def hooked(b_id, value, *a, **k):
                state[b_id] = bool(value)
                return orig(b_id, value, *a, **k)
            dev.set_button = hooked
        except Exception as e:
            print("[HUD Warning] vJoyボタンの監視を付けられません: {}".format(e))

    def set_cece27(self, state):
        self.is_cece27_active = bool(state)

    def set_hud_swap_yaw_roll(self, state):
        self.hud_swap_yaw_roll = bool(state)

    def _clamp_vjoy(self, value):
        return max(0, min(0x8000, int(value)))

    @property
    def joystick_grabbed(self):
        try:
            return self._joystick_grabbed
        except AttributeError:
            return False

    @joystick_grabbed.setter
    def joystick_grabbed(self, x):
        self._joystick_grabbed = bool(x)
        if x:
            self.grabbable_x.grabbed()
            self.grabbable_y.grabbed()
            self.grabbable_z.grabbed()
        else:
            self.grabbable_x.ungrabbed()
            self.grabbable_y.ungrabbed()
            self.grabbable_z.ungrabbed()

            self.grabbable_x.reset_to_center()
            self.grabbable_y.reset_to_center()
            self.grabbable_z.reset_to_center()
            self.grab_base_q = None

    def set_trackpad_touch_left(self):
        self.left_touchpad_touched = True

    def set_trackpad_untouch_left(self):
        self.left_touchpad_touched = False

    def set_trackpad_touch_right(self):
        self.right_touchpad_touched = True

    def set_trackpad_untouch_right(self):
        self.right_touchpad_touched = False

    def set_button_touch(self, button, hand):
        if hand == 'left':
            self.left_touched_buttons.add(button)
        elif hand == 'right':
            self.right_touched_buttons.add(button)

    def set_button_untouch(self, button, hand):
        if hand == 'left':
            self.left_touched_buttons.discard(button)
        elif hand == 'right':
            self.right_touched_buttons.discard(button)

    def set_touch_mask(self, hand, mask):
        if hand == 'left':
            self.left_touch_mask = int(mask)
        elif hand == 'right':
            self.right_touch_mask = int(mask)

    def _is_left_touched(self, button_id):
        if button_id in self.left_touched_buttons:
            return True
        return bool((self.left_touch_mask >> button_id) & 1)

    def set_button_press(self, button, hand):
        super().set_button_press(button, hand)
        if hand == 'left':
            if button == openvr.k_EButton_Grip:
                self.throttle_z.grabbed()
                self.throttle_x.grabbed()
                self.throttle_y.grabbed()
            elif button == openvr.k_EButton_ApplicationMenu:
                self.left_app_menu_pressed = True

        if hand == 'right' and button == openvr.k_EButton_Grip:
            if self.config.joystick_grabbing_switch:
                self.joystick_grabbed = not self.joystick_grabbed
            else:
                self.joystick_grabbed = True

    def set_button_unpress(self, button, hand):
        super().set_button_unpress(button, hand)
        if hand == 'left':
            if button == openvr.k_EButton_Grip:
                self.throttle_z.ungrabbed()
                self.throttle_x.ungrabbed()
                self.throttle_y.ungrabbed()
            elif button == openvr.k_EButton_ApplicationMenu:
                self.left_app_menu_pressed = False

        if hand == 'right' and button == openvr.k_EButton_Grip and (not self.config.joystick_grabbing_switch):
            self.joystick_grabbed = False

    def _update_joystick_normal(self, axisX, axisY, axisZ):
        vx = self._clamp_vjoy(axisX * 0x8000)
        vy = self._clamp_vjoy(axisY * 0x8000)
        vz = self._clamp_vjoy(axisZ * 0x8000)
        self.device.set_axis(HID_USAGE_X, vx)
        self.device.set_axis(HID_USAGE_Y, vy)
        self.device.set_axis(HID_USAGE_Z, vz)
        return vx / float(0x8000), vy / float(0x8000), vz / float(0x8000)

    def _update_grabbable_joystick(self, axisX, axisY, axisZ):
        self.grabbable_x.update(axisX)
        self.grabbable_y.update(axisY)
        self.grabbable_z.update(axisZ)

        self.device.set_axis(HID_USAGE_X, self._clamp_vjoy(self.grabbable_x.x * 0x8000))
        self.device.set_axis(HID_USAGE_Y, self._clamp_vjoy(self.grabbable_y.x * 0x8000))
        self.device.set_axis(HID_USAGE_Z, self._clamp_vjoy(self.grabbable_z.x * 0x8000))
        return self.grabbable_x.x, self.grabbable_y.x, self.grabbable_z.x

    def _set_pov(self, value, pov_id=1):
        if hasattr(self.device, 'set_cont_pov'):
            self.device.set_cont_pov(value, pov_id)
        elif hasattr(self.device, '_sdk') and hasattr(self.device._sdk, 'SetContPov'):
            self.device._sdk.SetContPov(int(value), self.device.rID, int(pov_id))

    def _update_pad_and_pov(self, left_ctr, right_ctr):
        povtouchfind = (
            self.left_app_menu_pressed
            or (openvr.k_EButton_ApplicationMenu in self.left_touched_buttons)
            or self.left_touchpad_touched
            or any(self._is_left_touched(i) for i in self.pov_touch_ids)
        )

        is_pov_mode = (povtouchfind != self.joysticknotouchpov)
        self.is_pov_mode = is_pov_mode
        rx = getattr(right_ctr, 'trackpadX', 0.0)
        ry = getattr(right_ctr, 'trackpadY', 0.0)
        direction = self.dpad.update(rx, ry)

        if direction == 5:
            self._dpad_dbg_out = '-'
            for b_id in self.pov_buttons:
                self.device.set_button(b_id, False)
            self._set_pov(-1, 1)
            return

        if is_pov_mode:
            for b_id in self.pov_buttons:
                self.device.set_button(b_id, False)

            pov_angle_map = {
                8: 0, 9: 4500, 6: 9000, 3: 13500,
                2: 18000, 1: 22500, 4: 27000, 7: 31500,
            }
            angle = pov_angle_map.get(direction, -1)
            self._dpad_dbg_out = str(angle)
            self._set_pov(angle, 1)
        else:
            self._set_pov(-1, 1)
            btn_up, btn_down, btn_left, btn_right = self.pov_buttons
            button_map = {
                8: [btn_up],
                6: [btn_right],
                2: [btn_down],
                4: [btn_left],
            }
            active_buttons = button_map.get(direction, [])
            self._dpad_dbg_out = ' '.join(str(b) for b in active_buttons) if active_buttons else 'NONE'
            for b_id in self.pov_buttons:
                self.device.set_button(b_id, b_id in active_buttons)

    def _load_pivot_file(self):
        try:
            if os.path.exists(THROTTLE_PIVOT_FILE):
                with open(THROTTLE_PIVOT_FILE, 'r', encoding='utf-8') as f:
                    o = json.load(f)['offset']
                self.throttle_pivot_offset = (float(o[0]), float(o[1]), float(o[2]))
                self._pivot_source = 'file'
                print("[Throttle] 計測済みオフセットを読込: {}".format(self.throttle_pivot_offset))
        except Exception as e:
            print("[Throttle] throttle_pivot.json の読込に失敗: {}".format(e))

    def _save_pivot_file(self):
        try:
            with open(THROTTLE_PIVOT_FILE, 'w', encoding='utf-8') as f:
                json.dump({'offset': list(self.throttle_pivot_offset)}, f)
        except Exception as e:
            print("[Throttle] throttle_pivot.json の保存に失敗: {}".format(e))

    def _haptic(self, ctr, times=1):
        """振動パルス。2回目以降はタイマーで遅らせ、60Hzのループを止めない。"""
        try:
            idx = _device_index(ctr)
            for n in range(times):
                if n == 0:
                    openvr.VRSystem().triggerHapticPulse(idx, 0, 3000)
                else:
                    threading.Timer(0.25 * n, lambda: openvr.VRSystem().triggerHapticPulse(idx, 0, 3000)).start()
        except Exception:
            pass

    # ---------------------------------------------------------------- デバッグコマンド
    # キーボード以外 (SteamVR Wheel のメニューやコントローラーの操作など) からも同じ名前で呼べるようにしてある:
    #     joystick.debug_command('hud_stats')
    # 呼ぶのは Joystick.update() と同じスレッドから (今はキー入力もそこで処理している)。
    DEBUG_COMMANDS = [   # (名前, 説明)。並び順 = 一覧の表示順
        ('hud_recenter', "HUD 奥行き表示の基準の目の位置を今の頭の位置にする (このセッションだけ)"),
        ('hud_cycle_mode', "HUD の見せ方を 'fakefar' → 'far' → 'plate' の順に切り替える"),
        ('hud_stats', "HUD の統計を 5 秒ごとに表示 / やめる"),
        ('hud_diagnose', "頭の姿勢の届き方を 3 秒測る"),
        ('hud_shift_switch_vsync', "'fakefar' のずらしの切り替えを、コピー完了から 0→1→2→3 vsync 後に"),
        ('hud_shift_vsync_target', "'fakefar' のずらしの予測を「次に合成される画面が光る時刻」/「一定時間先」で切り替え"),
        ('hud_predict_down', "頭の位置の予測に足す時間を -2ms"),
        ('hud_predict_up', "頭の位置の予測に足す時間を +2ms"),
        ('hud_predict_reset', "頭の位置の予測に足す時間を 0 に戻す"),
        ('pivot_calibration', "左手首のピボット計測を予約 / 取り消し (throttle_pivot.json に保存)"),
        ('hud_log_cycle', "HUD のデバッグログ (操作インジゲータの上) を 普通 → 大きく → 隠す の順に切り替える"),
        ('hud_log_toggle', "HUD のデバッグログを隠す / 出す (出すときは隠す前の大きさ)"),
        ('hud_log_clear', "HUD のデバッグログを消す (コンソールの表示はそのまま)"),
        ('version', "システム名とバージョンを表示する (コンソール + HUD の中央に大きく)"),
        ('dpad_debug', "Q29-3 調査用: スティックと VirtualDPad の数値の段を出す / 隠す"),
        ('dpad_log', "Q29-3 調査用: VirtualDPad の方向が変わるたびの [DPAD] の1行ログを出す / 止める"),
        ('hud_late_shift_toggle', "HUD 揺れ調査用: 'fakefar' のずらし (HUD_LATE_SHIFT) を入 / 切"),
        ('hud_texture_freeze', "HUD 揺れ調査用: 'fakefar' の絵の描き直しを 通常 → 240 → 120 → 80 → 60 → 40 → 20 → 10 → 5 → 1 回/秒 に絞る (ずらしはそのまま)"),
        ('hud_jitter_csv', "HUD 揺れ調査用: 1枚ごとの時刻とずらし量の CSV の記録を始める / 止める"),
        ('hud_pose_thread', "検証用: 位置の計算を別スレッドで 切 → 姿勢だけ → 全部 (写し方・拡大縮小・ずらしも。描く側は読むだけ)"),
        ('hud_fixed_ref', "検証用: 'fakefar' の絵を基準の目の形で描き、頭の動きはずらしで直す (入 / 切)"),
        ('hud_crosshair', "検証用: 基準の目の真正面 (HUD の中心) の十字線を出す / 隠す"),
    ]

    def debug_command(self, name):
        """
        デバッグコマンドを名前で実行する。知っている名前なら True、知らなければ False (一覧を表示)。
        キーボード (DEBUG_KEYMAP) も、将来の SteamVR Wheel からの操作も、ここを通す。
        """
        hud = self.hud
        if name == 'hud_recenter':
            if hud is not None and hasattr(hud, 'recenter_depth'):
                hud.recenter_depth()
                print("[HUD] 視差の基準を今の頭の位置にしました")
        elif name == 'hud_cycle_mode':
            if hud is not None:
                hud.cycle_mode()
        elif name == 'hud_stats':
            if hud is not None:
                hud.toggle_stats()
        elif name == 'hud_diagnose':
            hud_tracking_diagnose()
        elif name == 'hud_shift_switch_vsync':
            hud_cycle_shift_switch_vsync()
        elif name == 'hud_shift_vsync_target':
            hud_toggle_shift_vsync_target()
        elif name == 'hud_predict_down':
            hud_adjust_predict_extra(-0.002)
        elif name == 'hud_predict_up':
            hud_adjust_predict_extra(0.002)
        elif name == 'hud_predict_reset':
            hud_adjust_predict_extra(None)
        elif name == 'pivot_calibration':
            if self._cal_phase is None:
                self._cal_phase = 'wait'
                self._cal_t = time.time()
                print("[Throttle] 計測予約: {:.0f}秒後に開始します。左コントローラーを持ってください".format(PIVOT_CAL_DELAY_SEC))
            else:
                self._cal_phase = None
                self._pivot_cal = None
                print("[Throttle] 計測をキャンセルしました")
        elif name == 'hud_log_cycle':
            m = HUD_LOG.cycle()
            print("[HUD] デバッグログ: {}".format({'normal': "普通", 'large': "大きく", 'hidden': "隠す"}.get(m, m)))
        elif name == 'hud_log_toggle':
            on = HUD_LOG.toggle()
            print("[HUD] デバッグログ: {}".format("出す" if on else "隠す"))
        elif name == 'hud_log_clear':
            HUD_LOG.clear()
        elif name == 'dpad_debug':
            self.dpad_debug_hud = not self.dpad_debug_hud
            print("[DPAD] 数値の段: {}".format("出す" if self.dpad_debug_hud else "隠す"))
        elif name == 'dpad_log':
            hud_toggle_dpad_log()
        elif name == 'hud_late_shift_toggle':
            hud_toggle_late_shift()
        elif name == 'hud_texture_freeze':
            hud_cycle_texture_freeze()
        elif name == 'hud_jitter_csv':
            hud_toggle_jitter_csv()
        elif name == 'hud_pose_thread':
            hud_toggle_pose_thread()
        elif name == 'hud_fixed_ref':
            hud_toggle_fixed_ref()
        elif name == 'hud_crosshair':
            hud_toggle_crosshair()
        elif name == 'version':
            print(app_version_text())
            if hud is not None and hasattr(hud, 'show_splash'):
                hud.show_splash()
        else:
            print("[Debug] 知らないコマンド '{}'。使えるもの: {}".format(
                name, ', '.join(n for n, _ in self.DEBUG_COMMANDS)))
            return False
        return True

    def _poll_calibration_key(self):
        """コンソールのキーを DEBUG_KEYMAP でデバッグコマンドに変えて実行する (Windows のみ)。"""
        if msvcrt is None:
            return
        try:
            keymap = dict((str(k).lower(), c) for k, c in DEBUG_KEYMAP)
            while msvcrt.kbhit():
                ch = msvcrt.getwch()
                cmd = keymap.get(ch.lower())
                if cmd:
                    self.debug_command(cmd)
        except Exception as e:
            print("[Debug] キー入力の処理に失敗: {}: {}".format(type(e).__name__, e))

    def _tick_calibration(self, left_ctr):
        if self._cal_phase is None:
            return
        now = time.time()
        if self._cal_phase == 'wait' and now - self._cal_t >= PIVOT_CAL_DELAY_SEC:
            self._cal_phase = 'record'
            self._cal_t = now
            self.start_throttle_pivot_calibration()
            self._haptic(left_ctr, 1)
        elif self._cal_phase == 'record' and now - self._cal_t >= PIVOT_CAL_RECORD_SEC:
            self._cal_phase = None
            o = self.finish_throttle_pivot_calibration()
            if o is not None:
                self._pivot_source = 'file'
                self._save_pivot_file()
            self._haptic(left_ctr, 2)

    @staticmethod
    def _pose_matrix(ctr):
        try:
            return ctr.pose.mDeviceToAbsoluteTracking
        except Exception:
            return None

    def _left_throttle_inputs(self, left_ctr):
        """手首ピボット補正した (y, z)。行列が取れない/オフセット0なら従来どおり left_ctr.y / .z。"""
        y, z = left_ctr.y, left_ctr.z
        self._poll_calibration_key()
        self._tick_calibration(left_ctr)
        if self._pivot_source == 'constant' and THROTTLE_REF_COMPONENT and not self._component_tried:
            self._component_tried = True
            o = query_component_offset(left_ctr, THROTTLE_REF_COMPONENT)
            if o is not None:
                self.throttle_pivot_offset = o
                self._pivot_source = 'component'
                print("[Throttle] レンダーモデル部品 '{}' の位置をオフセットに採用: ({:.4f}, {:.4f}, {:.4f}) m".format(
                    THROTTLE_REF_COMPONENT, *o))
            else:
                print("[Throttle] 部品 '{}' を取得できないため、THROTTLE_PIVOT_OFFSET を使用します".format(THROTTLE_REF_COMPONENT))
        m = self._pose_matrix(left_ctr)
        if m is None:
            return y, z
        if self._pivot_cal is not None:
            self._pivot_cal.add(m)
        ox, oy, oz = self.throttle_pivot_offset
        if ox == 0.0 and oy == 0.0 and oz == 0.0:
            return y, z
        y += m[1][0] * ox + m[1][1] * oy + m[1][2] * oz
        z += m[2][0] * ox + m[2][1] * oy + m[2][2] * oz
        return y, z

    def start_throttle_pivot_calibration(self):
        self._pivot_cal = PivotCalibrator()
        print("[Throttle] ピボット計測開始: 左手首を支点に、縦・横・ひねりを大きめに{:.0f}秒回してください (腕は動かさない)".format(PIVOT_CAL_RECORD_SEC) + "")

    def finish_throttle_pivot_calibration(self, apply=True):
        cal, self._pivot_cal = self._pivot_cal, None
        if cal is None:
            print("[Throttle] 計測は開始されていません")
            return None
        o, msg = cal.solve()
        if o is None:
            print("[Throttle] ピボット計測失敗: {}".format(msg))
            return None
        print("[Throttle] ピボットオフセット = ({:.4f}, {:.4f}, {:.4f}) m  (固定するなら THROTTLE_PIVOT_OFFSET に記入)".format(*o))
        if apply:
            self.throttle_pivot_offset = o
        return o

    @staticmethod
    def _controller_heading(ctr):
        """コントローラーのローカルx軸(右側)を水平面に落とした向き[rad]。
        どんな持ち方でも右側の軸はおおむね水平なので、持ち方に依らない基準になる。"""
        m = Joystick._pose_matrix(ctr)
        if m is None:
            return 0.0
        try:
            return math.atan2(-m[2][0], m[0][0])
        except Exception:
            return 0.0

    def _stick_outputs(self, q_curr):
        """つかんだ姿勢からの回転を (pitch, roll, yaw) の 0..1 出力にする。
        ワールド座標の回転ベクトルは x=右(ピッチ) / y=上(ヨー) / z=手前(ロール)。
        以前は y を「roll」、z を「yaw」と呼んでいたが、実際は逆だった (出力先の振り分けは結果的に正しかった)。"""
        q_rel = q_curr.multiply(self.grab_base_q.conjugate())
        rx, ry, rz = q_rel.to_rotation_vector_deg()
        if JOY_ALIGN_TO_GRAB_HEADING:
            c, s = math.cos(self.grab_heading), math.sin(self.grab_heading)
            rx, rz = rx * c - rz * s, rx * s + rz * c      # 縦軸まわりに -heading 回して軸をそろえる
        pitch = max(0.0, min(1.0, 0.5 + rx / (2.0 * self.max_angle_pitch)))
        roll = max(0.0, min(1.0, 0.5 + rz / (2.0 * self.max_angle_roll)))
        yaw = max(0.0, min(1.0, 0.5 + ry / (2.0 * self.max_angle_yaw)))
        return pitch, roll, yaw

    def _log_row(self):
        if not JOY_LOG_CSV:
            return
        try:
            if self._log_fp is None:
                self._log_fp = open(JOY_LOG_CSV, 'w', encoding='utf-8')
                self._log_fp.write('t,axisX_roll,axisY_pitch,axisZ_yaw,throttle,pov_mode,bmark\n')
            ax, ay, az = self._hud_axes
            self._log_fp.write('{:.3f},{:.4f},{:.4f},{:.4f},{:.4f},{},{}\n'.format(
                time.time(), ax, ay, az, self.throttle_z.x, int(self.is_pov_mode), int(self.left_app_menu_pressed)))
        except Exception:
            pass

    def _dpad_debug_values(self, left_ctr, right_ctr):
        """Q29-3 調査用: 数値の段に渡す辞書。DPAD_DEBUG_HUD_HZ の回数だけ作り直す (それ以外は前の辞書 = 描き直さない)。"""
        now = time.time()
        if self._dpad_dbg_vals and now - self._dpad_dbg_time < 1.0 / max(1.0, float(DPAD_DEBUG_HUD_HZ)):
            return self._dpad_dbg_vals
        self._dpad_dbg_time = now
        try:
            lx = float(getattr(left_ctr, 'trackpadX', 0.0))
            ly = float(getattr(left_ctr, 'trackpadY', 0.0))
            rx = float(getattr(right_ctr, 'trackpadX', 0.0))
            ry = float(getattr(right_ctr, 'trackpadY', 0.0))
            dp = self.dpad
            ang = dp.dbg_angle
            edge = abs(((ang - 22.5) % 45.0) - 22.5)    # 8 区画の境目 (22.5 + 45n) までの角度
            edge = 22.5 - edge
            self._dpad_dbg_vals = {
                'lx': lx, 'ly': ly, 'lr': math.sqrt(lx * lx + ly * ly),
                'rx': rx, 'ry': ry, 'rr': math.sqrt(rx * rx + ry * ry), 'ra': math.degrees(math.atan2(ry, rx)),
                'dist': dp.dbg_dist, 'ang': ang, 'edge': edge, 'th': dp.dbg_threshold,
                'dir': dp.current_dir, 'mode': 'POV' if self.is_pov_mode else 'BTN', 'out': self._dpad_dbg_out,
                'chg': dp.dbg_changes, 'ms': (now - dp.dbg_change_time) * 1000.0,
            }
        except Exception as e:
            print("[DPAD] Warning: 数値を作れませんでした: {}".format(e))
        return self._dpad_dbg_vals

    def update(self, left_ctr, right_ctr):
        super().update(left_ctr, right_ctr)

        if self.joystick_grabbed:
            q_curr = get_controller_quaternion(right_ctr)
            if self.grab_base_q is None:
                self.grab_base_q = q_curr
                self.grab_heading = self._controller_heading(right_ctr)

            pitch_output, roll_output, yaw_output = self._stick_outputs(q_curr)

            axisX = 1.0 - roll_output    # vJoy X = エルロン(ロール)
            axisY = pitch_output         # vJoy Y = エレベーター(ピッチ)
            axisZ = 1.0 - yaw_output     # vJoy Z = ラダー(ヨー)
        else:
            axisX = 0.5
            axisY = 0.5
            axisZ = 0.5

        if self.config.joystick_updates_only_when_grabbed:
            self._hud_axes = self._update_grabbable_joystick(axisX, axisY, axisZ)
        else:
            self._hud_axes = self._update_joystick_normal(axisX, axisY, axisZ)

        self._update_pad_and_pov(left_ctr, right_ctr)

        thr_y, thr_z = self._left_throttle_inputs(left_ctr)
        self.throttle_z.update(thr_z)
        self.throttle_y.update(thr_y)
        self.throttle_x.update(left_ctr.yaw)

        self.device.set_axis(HID_USAGE_RZ, self._clamp_vjoy(self.throttle_z.x * 0x8000))
        self.device.set_axis(HID_USAGE_RY, self._clamp_vjoy(self.throttle_y.x * 0x8000))
        self.device.set_axis(HID_USAGE_RX, self._clamp_vjoy(self.throttle_x.x * 0x8000))

        self._log_row()

        # リミッターの制限値（80%）を超えている間だけ、スロットルバーを黄色(#CECE27)にする
        # (信号 'sig:throttle_over_limit'。HUD_BAR_YELLOW_WHEN に入っている)
        is_over_limit = THROTTLE_ACCELERATOR_LIMITTER and (self.throttle_z.x > THROTTLE_ACCEL_LIMIT_RATIO)

        if self.hud:
            ax, ay, az = self._hud_axes
            hud_roll = (ax - 0.5) * 2.0
            hud_yaw = (az - 0.5) * 2.0
            if self.hud_swap_yaw_roll:
                hud_yaw, hud_roll = hud_roll, hud_yaw
            self.hud.update_hud_state(
                throttle_val=self.throttle_z.x,
                pitch_val=(ay - 0.5) * 2.0,
                roll_val=hud_roll,
                yaw_val=hud_yaw,
                bmark_pressed=self.left_app_menu_pressed,
                cece27_toggle=self.is_cece27_active,
                pov_mode=self.is_pov_mode,
                signals={'sig:throttle_over_limit': is_over_limit,
                         'sig:stick_grab': self._joystick_grabbed,
                         'sig:throttle_grab': self.throttle_z.throttle_grabbed,
                         'sig:cruise': bool(CRUISE_MODE_ENABLED),
                         'sig:dpad_debug': self.dpad_debug_hud},
                buttons=self._vbtn_state,
                values={'throttle': self.throttle_z.x,
                        'cruise_power': CRUISE_MODE_Power if CRUISE_MODE_Power is not None else self.throttle_z.x,
                        'cruise_center': self.cruise_center,
                        'dbg': self._dpad_debug_values(left_ctr, right_ctr) if self.dpad_debug_hud else None}
            )