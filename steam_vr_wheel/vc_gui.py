# -*- coding: utf-8 -*-
"""
VC コンソール (vc_gui.py): PC の画面に出す設定とログの窓。別プロセスで動く。

■ これは何か
  - 古い configurator.py (wxPython) を広げた窓。ログ・設定・プロファイル・パネルを 1 つの窓にまとめる。
  - ジョイスティック本体 (_joystick.py の 60 Hz のループ) とは別のプロセス。ここで止まっても本体には触れない。
  - Python 3.5 / wxPython 4.0.x で動く書き方だけを使う (f 文字列・型注釈・:= は使わない)。

■ 起動
  - リポジトリの直下で:  python -m steam_vr_wheel.vc_gui [--profile ファイル名] [--log ログのパス]
  - または:             python vc_gui.py [--profile ファイル名] [--log ログのパス]
  - _joystick.py が pythonw -m steam_vr_wheel.vc_gui で起動する (その部分は _joystick.py 側。[CONFIG] のフラグが True のとき)。
  - 二重起動はしない (wx.SingleInstanceChecker)。もう 1 つ動いていたら、何も言わずに終わる。
  - --profile: プロファイルのタブで最初に選ぶファイル (省略時は default.json)。ファイル名だけの引数も同じ意味 (古い書き方)。
  - --log: 読むログのパス (省略時は <このフォルダ>/media/vc_log.txt)。
  - --status / --cmd / --alive: コクピット本体 (_joystick.py) との受け渡しファイル (下の「コクピットとの受け渡し」)。省略時は <このフォルダ>/media/ の既定の名前。
  - 前の起動のまま開いている窓は、新しい本体にも使い回される。だから pid などを引数から覚えず、状態は毎回 status ファイルから読む。
  - ログは _joystick.py が 1 行ずつ (完全な行、UTF-8、改行は \n) 足す。ジョイスティックの起動時と、8 MB を超えたときに空にされる。

■ タブ (どのタブでも、窓の上にコクピットの状態の 1 行が出る)
  0. コクピット  動いているコクピットの操作 (プロファイルの切り替え・読み直し・コンソールの出し隠し・デバッグ命令)。
  1. ログ       media/vc_log.txt を 250 ms ごとに読み足して出す。絞り込み・一時停止・消す・フォルダを開く。
  2. 設定       古い configurator と同じ項目。steam_vr_wheel.PadConfig 経由で読み書きし、変えたらすぐ保存する。
  3. プロファイル  profiles/*.json の "settings" を型つきの部品で編集する。書かないキーは書かないまま (= コードの既定)。
  4. パネル     "panels" (left_game / right_game) の木と項目のフォームと丸い見本 (左右 2 つ並べる)。警告の一覧は変えるたびに作り直す。

■ コクピットとの受け渡し (0.1.2。形は _joystick.py v0.1.44 と合わせてある)
  - 読む: media/vc_status.json  本体が約 1 秒ごと (と変わったとき) に書く。
      {"format":"vc-status","format_version":1,"pid","app_version","profile_file","profile_name","profiles":[...],"config_mode","console_hidden","time"}
      time が 5 秒より古い、またはファイルが無いときは「止まっている」とみなす (STATUS_STALE_SEC)。
  - 書く (足す): media/vc_cmd.txt  1 行に JSON 1 つ (UTF-8、\n 終わり)。毎回、追記モードで開く。
      {"cmd":"profile_load","file":"x.json"} / {"cmd":"profile_reload"} / {"cmd":"debug","name":"hud_recenter"} / {"cmd":"console","show":true} / {"cmd":"quit"}
  - 書く (上書き): media/vc_gui_alive.txt  1 秒ごとに str(time.time())。本体はこれが新しい間だけ黒いコンソールを隠す。
      閉じるときは消す (消せなければ 0 を書く)。wx.Timer (TICK_MS) で書く。
  - 保存したプロファイルが本体の今のプロファイルなら、自動で profile_reload を送る。
  - 窓を閉じるとき、コクピットが動いていれば「コクピットも終了する / この窓だけ閉じる / キャンセル」を聞く。

■ ファイルの受け渡し (契約)
  - 読む: <このファイルのフォルダ>/media/vc_log.txt   (UTF-8、_joystick.py が 1 行ずつ足す。ジョイスティックの起動時に空にされる)
  - 読む/書く: <このファイルのフォルダ>/profiles/*.json  (format = 'vc-profile'、format_version = 1)
      保存の前に <名前>.json.bak へ古い中身を写す。知らないキーはそのまま残す。
      キーの順は format, format_version, profile, settings, input, panels、項目は label, type, folder, command, args, exec, hold, block_a, hud。
      保存した中身は、ジョイスティックがプロファイルを読み直したとき (N キーで切り替え、または再起動) に効く。
  - 読む/書く: media/config.json (PadConfig が管理。古い設定タブだけが触る)
  - ファイルまわりは全部 try/except。失敗しても落とさず、状態バーに 1 行出す。

■ 作りの方針
  - 部品 (読み込み・並べ替え・警告の判定・ログの追いかけ) は wx に頼らない関数とクラスにしてある (テストしやすい)。
  - 警告の文は _joystick.py の load_input_profile / _read_panel_side と同じ決まりで数える (項目の数 n、届かない番号など)。
    _joystick.py の決まりを変えたら、validate_panels() も合わせる。
"""
import collections
import io
import json
import os
import sys
import time

import wx

VC_GUI_VERSION = '0.1.2'

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(PACKAGE_DIR, 'media', 'vc_log.txt')
PROFILE_DIR = os.path.join(PACKAGE_DIR, 'profiles')
STATUS_PATH = os.path.join(PACKAGE_DIR, 'media', 'vc_status.json')      # 本体が書く状態
CMD_PATH = os.path.join(PACKAGE_DIR, 'media', 'vc_cmd.txt')             # この窓が足す命令
ALIVE_PATH = os.path.join(PACKAGE_DIR, 'media', 'vc_gui_alive.txt')     # この窓が 1 秒ごとに書く生存の印
DEFAULT_PROFILE_FILE = 'default.json'

LOG_POLL_MS = 250                       # [CONFIG] ログを読みに行く間隔 (ミリ秒)
LOG_MAX_LINES = 3000                    # [CONFIG] 窓に残す行の数
LOG_FIRST_READ_MAX_BYTES = 512 * 1024   # [CONFIG] 最初に開いたとき、ファイルの終わりからこれだけ読む
LOG_READ_CHUNK_BYTES = 1024 * 1024      # [CONFIG] 1 回の読み込みの上限
STATUS_STALE_SEC = 5.0                  # [CONFIG] status の time がこれより古ければ「止まっている」
TICK_MS = 1000                          # [CONFIG] 生存の印を書く・状態を読む間隔 (ミリ秒)
WINDOW_SIZE = (1200, 780)               # [CONFIG] 窓の大きさ
PREVIEW_SIZE = 240                      # [CONFIG] パネルの見本の大きさ (画素。左右 2 つ並べる)
LABEL_OK_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 /.-+'   # [CONFIG] HUD の文字で出せるラベルの文字 (外れたら情報を出す)
NEW_ITEM_LABEL = 'NEW'                  # [CONFIG] スロットを足したときのラベル

PANEL_SLOT_MAX = 8                      # 1 つの階層に置けるスロットの数 (_joystick.py の PANEL_SLOTS)
PANEL_BACK_SLOT = '1'                   # 下の階層で「戻る」に予約されている番号
ITEM_KEY_ORDER = ['label', 'type', 'folder', 'command', 'args', 'exec', 'hold', 'block_a', 'latch', 'hud']
TOP_KEY_ORDER = ['format', 'format_version', 'profile', 'settings', 'input', 'panels']
PANEL_COMMANDS = ['vjoy_button', 'brake', 'cruise', 'config']   # 0.1.1: 'config' = コンフィグモードへ
CRUISE_ACTIONS = ['toggle', 'on', 'off', 'center']
HUD_MARKS = ['mnvr', 'brake']
VJOY_AXES = ['HID_USAGE_X', 'HID_USAGE_Y', 'HID_USAGE_Z', 'HID_USAGE_RX',
             'HID_USAGE_RY', 'HID_USAGE_RZ', 'HID_USAGE_SL0', 'HID_USAGE_SL1']

DEBUG_COMMANDS = [('hud_recenter', 'HUD を基準に合わせ直す'), ('version', 'バージョンを出す'),
                  ('drive_status', 'drive_status'), ('bus_status', 'bus_status')]   # 本体の debug 命令の名前

GRAY = (110, 110, 110)
RED = (190, 30, 30)
ORANGE = (170, 100, 0)
BLUE = (30, 80, 170)
GREEN = (30, 130, 60)


# ==============================================================================
# コクピット本体との受け渡し (wx に頼らない)
# ==============================================================================
def read_cockpit_status(path, now=None):
    """vc_status.json を読む。動いていれば dict、止まっている (無い・読めない・5 秒より古い) なら None。"""
    try:
        with io.open(path, 'r', encoding='utf-8') as f:
            st = json.load(f)
        if not isinstance(st, dict) or st.get('format') != 'vc-status':
            return None
        t = float(st.get('time'))
    except Exception:
        return None
    if now is None:
        now = time.time()
    if now - t > STATUS_STALE_SEC:
        return None
    return st


def send_cockpit_cmd(path, obj):
    """命令を 1 行の JSON にして追記する。返り値 = (成功か, 1 行)。"""
    try:
        line = json.dumps(obj, ensure_ascii=False) + '\n'
        with open(path, 'ab') as f:         # 毎回、追記モードで開く
            f.write(line.encode('utf-8'))
        return True, '命令を送りました: {}'.format(line.strip())
    except Exception as e:
        return False, '命令を送れません: {}'.format(e)


def write_alive(path):
    """生存の印 (今の時刻) を上書きする。失敗しても落とさず、成功かどうかだけ返す。"""
    try:
        with open(path, 'w') as f:
            f.write(str(time.time()))
        return True
    except Exception:
        return False


def clear_alive(path):
    """閉じるとき: 生存の印を消す。消せなければ 0 を書く。"""
    try:
        if os.path.exists(path):
            os.remove(path)
        return
    except Exception:
        pass
    try:
        with open(path, 'w') as f:
            f.write('0')
    except Exception:
        pass


def same_profile_file(path, profile_file):
    """path が profiles フォルダの profile_file (ファイル名) と同じファイルか。"""
    try:
        if not path or not profile_file:
            return False
        if os.path.basename(path).lower() != os.path.basename(str(profile_file)).lower():
            return False
        return os.path.normcase(os.path.abspath(os.path.dirname(path))) == os.path.normcase(os.path.abspath(PROFILE_DIR))
    except Exception:
        return False


# ==============================================================================
# 設定の部品の定義 (プロファイルの settings と、brake 項目の args の上書きで共有する)
# ==============================================================================
def _spec(key, title, kind, default, help_text, choices=None, lo=None, hi=None, step=None):
    return {'key': key, 'title': title, 'kind': kind, 'default': default, 'help': help_text,
            'choices': choices, 'lo': lo, 'hi': hi, 'step': step}


SETTING_SPECS = [
    _spec('throttle.mode', 'スロットルの方式', 'choice', 'A',
          'A = スロットルを vJoy の RZ に出す。B = ゲームパッド式 (アクセルが SL0、ブレーキが SL1)。', choices=['A', 'B']),
    _spec('throttle.b_center_neutral', 'B: 中央が中立', 'bool', True,
          'B モードで、レバーが 50% より上ならアクセル、下ならブレーキにする。'),
    _spec('brake.method', 'ブレーキの出し方', 'choice', 'pseudo',
          'pseudo = スロットル出力から引く (0 未満にならない)。axis = ブレーキ専用の軸に出す。button = ブレーキ中に vJoy のボタンを押す。',
          choices=['pseudo', 'axis', 'button']),
    _spec('brake.max', 'ブレーキの最大', 'float', 1.0, 'ブレーキの一番強い効き (0〜1)。', lo=0.0, hi=1.0, step=0.05),
    _spec('brake.curve', 'ブレーキの曲線', 'float', 1.0, '1 = 直線。1 より大きいと、引き始めはやわらかく効く (0.2〜5)。', lo=0.2, hi=5.0, step=0.1),
    _spec('brake.smooth_sec', 'ブレーキのなめらかさ', 'float', 0.08, 'トリガーに追いつくまでの時間 (秒)。0 = すぐ追いつく。', lo=0.0, hi=1.0, step=0.01),
    _spec('brake.start', 'ブレーキの効き始め', 'float', 0.10, 'ブレーキが効き始めるトリガーの値 (0〜0.9)。', lo=0.0, hi=0.9, step=0.01),
    _spec('brake.full', 'ブレーキの全開', 'float', 0.95, '全開のブレーキになるトリガーの値 (0.1〜1)。', lo=0.1, hi=1.0, step=0.01),
    _spec('brake.axis', 'ブレーキの軸', 'choice', 'HID_USAGE_SL1', 'method が axis のとき、ブレーキを出す vJoy の軸。', choices=VJOY_AXES),
    _spec('brake.button', 'ブレーキのボタン', 'int', 28, 'method が button のとき、押す vJoy のボタン番号 (1〜128)。', lo=1, hi=128, step=1),
    _spec('brake.button_on', 'ボタンを押す量', 'float', 0.5, 'ボタンを押すブレーキ量 (0〜1)。', lo=0.0, hi=1.0, step=0.05),
    _spec('cruise.double_click_sec', 'クルーズ: 二度引きの間隔', 'float', 0.40,
          'トリガーを 2 回引く間隔がこの秒数以内なら、クルーズの入り切り (0.1〜1.5)。', lo=0.1, hi=1.5, step=0.05),
    _spec('cruise.double_tilt_sec', 'クルーズ: 二度倒しの間隔', 'float', 0.60,
          'CRUISE の方向にスティックを 2 回倒す間隔がこの秒数以内なら、通常 / 中央クルーズの切り替え (0.1〜1.5)。', lo=0.1, hi=1.5, step=0.05),
    _spec('cruise.exit_on_move', 'クルーズ: 動かして終える', 'floatnull', None,
          'null = トリガーの二度引きだけでクルーズを終える。数値 = つかんだレバーがこれだけ動いても終える (0〜1)。', lo=0.0, hi=1.0, step=0.01),
    _spec('cruise.adjust', 'クルーズ: つかんだとき', 'choice', 'temporary',
          'temporary = つかんでいる間だけレバーの値 (離すと戻る)。set = 離したところを新しいクルーズの値にする。locked = 変わらない。',
          choices=['temporary', 'set', 'locked']),
]
SETTING_KEYS = [s['key'] for s in SETTING_SPECS]
BRAKE_ARG_SPECS = [s for s in SETTING_SPECS if s['key'].startswith('brake.')]
KNOWN_BRAKE_ARGS = [s['key'][len('brake.'):] for s in BRAKE_ARG_SPECS]


# ==============================================================================
# wx に頼らない部品: プロファイルの読み書き・並べ替え
# ==============================================================================
def read_json_ordered(path):
    """JSON を OrderedDict で読む (キーの順を保つ)。失敗したら例外。"""
    with io.open(path, 'r', encoding='utf-8') as f:
        return json.load(f, object_pairs_hook=collections.OrderedDict)


def _slot_sort_key(slot):
    s = str(slot)
    if s.isdigit():
        return (0, int(s), s)
    return (1, 0, s)


def order_item(item):
    """項目 (dict) のキーを決まった順に並べる。知らないキーは後ろにそのまま。"""
    if not isinstance(item, dict):
        return item
    out = collections.OrderedDict()
    for k in ITEM_KEY_ORDER:
        if k in item:
            out[k] = item[k]
    for k in item:
        if k not in out:
            out[k] = item[k]
    return out


def _order_table(table):
    if not isinstance(table, dict):
        return table
    out = collections.OrderedDict()
    for slot in sorted(table.keys(), key=_slot_sort_key):
        out[slot] = order_item(table[slot])
    return out


def _order_side(side, is_left):
    if not isinstance(side, dict):
        return side
    out = collections.OrderedDict()
    if is_left:
        if 'root' in side:
            out['root'] = side['root']
        if 'folders' in side:
            folders = side['folders']
            if isinstance(folders, dict):
                nf = collections.OrderedDict()
                for fname in folders:
                    nf[fname] = _order_table(folders[fname])
                out['folders'] = nf
            else:
                out['folders'] = folders
    else:
        if 'items' in side:
            out['items'] = _order_table(side['items'])
    for k in side:
        if k not in out:
            out[k] = side[k]
    return out


def order_profile(data):
    """保存用に、プロファイル全体のキーを決まった順に並べた OrderedDict を返す。"""
    if not isinstance(data, dict):
        return data
    out = collections.OrderedDict()
    for k in TOP_KEY_ORDER:
        if k not in data:
            continue
        if k == 'panels' and isinstance(data[k], dict):
            p = data[k]
            np_ = collections.OrderedDict()
            if 'left_game' in p:
                np_['left_game'] = _order_side(p['left_game'], True)
            if 'right_game' in p:
                np_['right_game'] = _order_side(p['right_game'], False)
            for pk in p:
                if pk not in np_:
                    np_[pk] = p[pk]
            out[k] = np_
        else:
            out[k] = data[k]
    for k in data:
        if k not in out:
            out[k] = data[k]
    return out


def write_profile_file(path, data):
    """data を整えて UTF-8 の JSON で書く。書く前に古いファイルを <path>.bak へ写す。
    返り値 = バックアップを作ったか。失敗したら例外。"""
    text = json.dumps(order_profile(data), ensure_ascii=False, indent=2) + '\n'
    made_bak = False
    if os.path.exists(path):
        with open(path, 'rb') as f:
            old = f.read()
        with open(path + '.bak', 'wb') as f:
            f.write(old)
        made_bak = True
    tmp = path + '.tmp'
    with io.open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    os.replace(tmp, path)
    return made_bak


def list_profile_files():
    """PROFILE_DIR の *.json のファイル名を名前順で返す。"""
    try:
        return sorted(n for n in os.listdir(PROFILE_DIR) if n.lower().endswith('.json'))
    except Exception:
        return []


class ProfileModel(object):
    """今開いているプロファイル (data) とファイルの場所 (path)。2 つのタブ (プロファイル・パネル) が共有する。"""

    def __init__(self):
        self.path = None
        self.data = collections.OrderedDict()
        self.dirty = False

    def load(self, path):
        """読む。返り値 = (成功か, 状態バーに出す 1 行)。失敗したら今の中身は変えない。"""
        try:
            data = read_json_ordered(path)
        except Exception as e:
            return False, '読めません: {}: {}'.format(os.path.basename(path), e)
        if not isinstance(data, collections.OrderedDict):
            return False, '読めません: {} の外側が {{ }} の形ではありません'.format(os.path.basename(path))
        self.path = path
        self.data = data
        self.dirty = False
        note = ''
        if data.get('format') != 'vc-profile' or data.get('format_version') != 1:
            note = ' (format が vc-profile / 1 ではないので、ジョイスティックは読みません)'
        return True, '読み込みました: {}{}'.format(os.path.basename(path), note)

    def save(self, path=None):
        """書く。返り値 = (成功か, 1 行)。"""
        path = path or self.path
        if not path:
            return False, '保存先がありません'
        try:
            bak = write_profile_file(path, self.data)
        except Exception as e:
            return False, '保存できません: {}: {}'.format(os.path.basename(path), e)
        self.path = path
        self.dirty = False
        return True, '保存しました: {}{}。ジョイスティックが読み直したとき (N キーで切り替え、または再起動) に効きます'.format(
            os.path.basename(path), ' (古い中身は .bak に写しました)' if bak else '')

    def settings(self, create=False):
        """settings の dict を返す。無ければ create=True で作る。dict でなければ None。"""
        s = self.data.get('settings')
        if isinstance(s, dict):
            return s
        if s is None and create:
            s = collections.OrderedDict()
            self.data['settings'] = s
            return s
        return None


# ------------------------------------------------------------------------------
# パネルの表を触る道具 (data['panels'] の中を探す)
# ------------------------------------------------------------------------------
def panel_root_name(data):
    p = data.get('panels')
    if isinstance(p, dict) and isinstance(p.get('left_game'), dict):
        return str(p['left_game'].get('root', 'main'))
    return 'main'


def get_side(data, side, create=False):
    """side = 'left' か 'right'。そのパネルの dict を返す。create=True なら無いときに作る。"""
    panels = data.get('panels')
    if not isinstance(panels, dict):
        if not create:
            return None
        panels = collections.OrderedDict()
        data['panels'] = panels
    key = 'left_game' if side == 'left' else 'right_game'
    sd = panels.get(key)
    if not isinstance(sd, dict):
        if not create:
            return None
        sd = collections.OrderedDict()
        if side == 'left':
            sd['root'] = 'main'
            sd['folders'] = collections.OrderedDict()
            sd['folders']['main'] = collections.OrderedDict()
        else:
            sd['items'] = collections.OrderedDict()
        panels[key] = sd
    return sd


def get_folders(data, create=False):
    """左パネルの folders (dict) を返す。"""
    sd = get_side(data, 'left', create)
    if sd is None:
        return None
    f = sd.get('folders')
    if not isinstance(f, dict):
        if not create:
            return None
        f = collections.OrderedDict()
        sd['folders'] = f
    return f


def get_table(data, side, fname, create=False):
    """階層 1 つ分の {スロット: 項目} を返す。右は fname を見ない。"""
    if side == 'left':
        folders = get_folders(data, create)
        if folders is None:
            return None
        t = folders.get(fname)
        if not isinstance(t, dict):
            if not create:
                return None
            t = collections.OrderedDict()
            folders[fname] = t
        return t
    sd = get_side(data, 'right', create)
    if sd is None:
        return None
    t = sd.get('items')
    if not isinstance(t, dict):
        if not create:
            return None
        t = collections.OrderedDict()
        sd['items'] = t
    return t


def is_root_level(data, side, fname):
    return side == 'right' or fname == panel_root_name(data)


def valid_slots(table, is_root):
    """_joystick.py が捨てずに残す番号 (1〜8、下の階層の 1 は除く) を数字順で返す。"""
    out = []
    for slot in table:
        s = str(slot)
        if s not in [str(i) for i in range(1, PANEL_SLOT_MAX + 1)]:
            continue
        if not is_root and s == PANEL_BACK_SLOT:
            continue
        if not isinstance(table[slot], dict):
            continue
        out.append(s)
    return sorted(out, key=_slot_sort_key)


def level_entries(data, side, fname):
    """見本用: その階層の 1〜n 番を [(文字, 種類)] で返す。種類 = item/folder/none/rest/missing/back。"""
    table = get_table(data, side, fname)
    if table is None:
        return []
    root = is_root_level(data, side, fname)
    vs = valid_slots(table, root)
    n = len(vs) + (0 if root else 1)
    out = []
    for k in range(1, n + 1):
        if not root and k == 1:
            out.append(('BACK', 'back'))
            continue
        row = table.get(str(k))
        if not isinstance(row, dict):
            out.append(('', 'missing'))
            continue
        t = row.get('type')
        if t == 'NONE':
            kind = 'none'
        elif t == 'REST':
            kind = 'rest'
        elif row.get('folder') is not None:
            kind = 'folder'
        else:
            kind = 'item'
        out.append((str(row.get('label', '')), kind))
    return out


# ------------------------------------------------------------------------------
# 警告の判定 (load_input_profile / _read_panel_side と同じ決まり)
# ------------------------------------------------------------------------------
def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _check_item(where, row, is_left, out):
    known = set(ITEM_KEY_ORDER)
    for k in row:
        if k not in known:
            out.append(('warn', where, "知らないキー '{}' (そのまま残します)".format(k)))
    t = row.get('type')
    if t is not None and t not in ('NONE', 'REST'):
        out.append(('warn', where, "type は 'NONE' か 'REST' だけです ({!r})".format(t)))
    label = row.get('label')
    if label is not None:
        bad = sorted(set(c for c in str(label) if c not in LABEL_OK_CHARS))
        if bad:
            out.append(('info', where, 'ラベルに HUD の文字で出せない字があります: {} (A-Z 0-9 空白 / . - + だけ)'.format(' '.join(bad)[:20])))
    if 'folder' in row and not is_left:
        out.append(('warn', where, '右パネルの項目に folder は書けません (捨てられます)'))
    if 'exec' in row:
        if is_left:
            out.append(('warn', where, "exec は右パネルだけの項目です (左では効きません)"))
        elif row['exec'] not in ('tilt', 'trigger'):
            out.append(('warn', where, "exec は 'tilt' か 'trigger' です ({!r})".format(row['exec'])))
    for k in ('hold', 'block_a', 'latch'):
        if k in row and not isinstance(row[k], bool):
            out.append(('warn', where, '{} は true / false です ({!r})'.format(k, row[k])))
    if 'hud' in row and row['hud'] not in HUD_MARKS:
        out.append(('warn', where, "hud は 'mnvr' か 'brake' です ({!r})".format(row['hud'])))
    cmd = row.get('command')
    args = row.get('args')
    if args is not None and not isinstance(args, dict):
        out.append(('warn', where, 'args は { } の形で書いてください'))
        args = None
    args = args or {}
    if cmd is None:
        if args:
            out.append(('info', where, 'command が無いので args は使われません'))
        return
    if cmd not in PANEL_COMMANDS:
        out.append(('warn', where, "パネルの項目に書ける命令は {} だけです ({!r})".format(', '.join(PANEL_COMMANDS), cmd)))
        return
    if cmd == 'vjoy_button':
        nums = None
        if isinstance(args.get('buttons'), list):
            nums = args['buttons']
        elif 'button' in args:
            nums = [args['button']]
        if not nums:
            out.append(('warn', where, 'vjoy_button に button か buttons がありません'))
        else:
            for b in nums:
                if not _is_int(b) or b < 1 or b > 128:
                    out.append(('warn', where, 'ボタン番号は 1〜128 の整数です ({!r})'.format(b)))
    elif cmd == 'brake':
        for k in args:
            if k not in KNOWN_BRAKE_ARGS:
                out.append(('warn', where, "brake の args に知らないキー '{}'".format(k)))
        for s in BRAKE_ARG_SPECS:
            k = s['key'][len('brake.'):]
            if k not in args:
                continue
            v = args[k]
            if s['kind'] == 'choice':
                if v not in s['choices']:
                    out.append(('warn', where, '{} は {} のどれかです ({!r})'.format(k, '/'.join(s['choices']), v)))
            elif not _is_num(v) or v < s['lo'] or v > s['hi']:
                out.append(('warn', where, '{} は {}〜{} の数です ({!r})'.format(k, s['lo'], s['hi'], v)))
    elif cmd == 'cruise':
        act = args.get('action', 'toggle')
        if act not in CRUISE_ACTIONS:
            out.append(('warn', where, "cruise の action は {} のどれかです ({!r})".format(', '.join(CRUISE_ACTIONS), act)))


def _check_table(side_label, fname, table, root, is_left, out):
    """階層 1 つ分。_read_panel_side と同じ決まりで、捨てられる行と届かない番号を数える。"""
    kept = []
    for slot in table:
        s = str(slot)
        where = '{} {}/{}'.format(side_label, fname, s)
        if s == '0':
            out.append(('warn', where, "スロット '0' は中央 (何もしない) なので書けません。捨てられます"))
            continue
        if s not in [str(i) for i in range(1, PANEL_SLOT_MAX + 1)]:
            out.append(('warn', where, "スロット '{}' は使えません (1〜{} だけ)。捨てられます".format(s, PANEL_SLOT_MAX)))
            continue
        if not root and s == PANEL_BACK_SLOT:
            out.append(('warn', where, "下の階層の '1' は「戻る」の予約なので書けません。捨てられます"))
            continue
        row = table[slot]
        if not isinstance(row, dict):
            out.append(('warn', where, '項目は { } の形で書いてください。捨てられます'))
            continue
        kept.append(s)
        _check_item(where, row, is_left, out)
    n = len(kept) + (0 if root else 1)
    for s in sorted(kept, key=_slot_sort_key):
        if int(s) > n:
            out.append(('warn', '{} {}/{}'.format(side_label, fname, s),
                        '届きません (項目は {} 個なので 1〜{} 番だけ選べる。空きは NONE で埋める)'.format(n, n)))
    return kept


def validate_panels(data):
    """プロファイルの panels を調べて [(重さ, 場所, 文)] を返す。重さ = 'error' / 'warn' / 'info'。"""
    out = []
    if not isinstance(data, dict):
        return [('error', '全体', 'プロファイルの外側が { } の形ではありません')]
    panels = data.get('panels')
    if panels is None:
        return [('info', 'panels', 'panels がありません (パネル無しで動きます)')]
    if not isinstance(panels, dict):
        return [('error', 'panels', "panels は {'left_game': ..., 'right_game': ...} の形で書いてください")]
    for k in panels:
        if k not in ('left_game', 'right_game'):
            out.append(('warn', 'panels', "知らないキー '{}' (そのまま残します)".format(k)))
    if 'left_game' in panels:
        side = panels['left_game']
        if not isinstance(side, dict):
            out.append(('error', 'left_game', 'パネルの中身は { } の形で書いてください'))
        else:
            for k in side:
                if k not in ('root', 'folders'):
                    out.append(('warn', 'left_game', "知らないキー '{}'".format(k)))
            root = str(side.get('root', 'main'))
            folders = side.get('folders') or {}
            if not isinstance(folders, dict):
                out.append(('error', 'left_game', 'folders は {フォルダ名: {スロット: 項目}} の形で書いてください'))
            else:
                if root not in folders:
                    out.append(('warn', 'left_game', "ルートのフォルダ '{}' がありません (空のルートとして動きます)".format(root)))
                tables = {}
                for fname in folders:
                    if not isinstance(folders[fname], dict):
                        out.append(('warn', 'left ' + str(fname), 'フォルダは {スロット: 項目} の形で書いてください。捨てられます'))
                        continue
                    kept = _check_table('left', fname, folders[fname], fname == root, True, out)
                    tables[fname] = dict((s, folders[fname][s]) for s in kept)
                _check_folder_links(root, tables, out)
    if 'right_game' in panels:
        side = panels['right_game']
        if not isinstance(side, dict):
            out.append(('error', 'right_game', 'パネルの中身は { } の形で書いてください'))
        else:
            for k in side:
                if k not in ('items',):
                    out.append(('warn', 'right_game', "知らないキー '{}'{}".format(
                        k, ' (右パネルにフォルダは書けません。捨てられます)' if k == 'folders' else '')))
            items = side.get('items') or {}
            if not isinstance(items, dict):
                out.append(('error', 'right_game', 'items は {スロット: 項目} の形で書いてください'))
            else:
                _check_table('right', 'items', items, True, False, out)
    return out


def _check_folder_links(root, tables, out):
    """folder の指す先が無い・循環している・ルートから届かないフォルダを調べる。"""
    seen = set([root])

    def visit(name, path):
        for slot in sorted(tables.get(name, {}).keys(), key=_slot_sort_key):
            row = tables[name][slot]
            target = row.get('folder')
            if target is None:
                continue
            target = str(target)
            where = 'left {}/{}'.format(name, slot)
            if target not in tables:
                out.append(('warn', where, "folder が指す '{}' がありません。この行は捨てられます".format(target)))
            elif target in path:
                out.append(('warn', where, "folder '{}' が循環しています。この行は捨てられます".format(target)))
            else:
                seen.add(target)
                visit(target, path + [target])

    visit(root, [root])
    for fname in tables:
        if fname not in seen:
            out.append(('info', 'left ' + str(fname), 'ルートから届かないフォルダです'))


# ------------------------------------------------------------------------------
# ログの追いかけ (wx に頼らない)
# ------------------------------------------------------------------------------
class LogTail(object):
    """ファイルの終わりを追いかけて、足された行を返す。縮んだら (= ジョイスティックの再起動) 先頭から読み直す。"""

    def __init__(self, path):
        self.path = path
        self.pos = 0
        self.partial = b''
        self.started = False
        self.skip_first = False
        self.had_file = False

    def poll(self):
        """返り値 = (ファイルがあるか, 最初から読み直したか, 新しい行のリスト)。ファイルの読み書きの失敗は例外のまま返す。"""
        try:
            size = os.path.getsize(self.path)
        except OSError:
            reset = self.had_file
            self.had_file = False
            self.pos = 0
            self.partial = b''
            self.started = False
            return False, reset, []
        self.had_file = True
        reset = False
        if not self.started:
            self.started = True
            if size > LOG_FIRST_READ_MAX_BYTES:
                self.pos = size - LOG_FIRST_READ_MAX_BYTES
                self.skip_first = True
            else:
                self.pos = 0
        elif size < self.pos:
            reset = True
            self.pos = 0
            self.partial = b''
            self.skip_first = False
        if size == self.pos:
            return True, reset, []
        with open(self.path, 'rb') as f:
            f.seek(self.pos)
            chunk = f.read(min(size - self.pos, LOG_READ_CHUNK_BYTES))
        self.pos += len(chunk)
        parts = (self.partial + chunk).split(b'\n')
        self.partial = parts.pop()
        if self.skip_first:
            if parts:
                parts.pop(0)
                self.skip_first = False
            else:
                self.partial = b''
        lines = [p.decode('utf-8', 'replace').rstrip('\r') for p in parts]
        return True, reset, lines


# ==============================================================================
# wx の部品
# ==============================================================================
def _gray(st):
    st.SetForegroundColour(wx.Colour(*GRAY))
    return st


def _bold(st):
    f = st.GetFont()
    f.SetWeight(wx.FONTWEIGHT_BOLD)
    st.SetFont(f)
    return st


def _fmt_default(v):
    if v is None:
        return 'null'
    if v is True:
        return 'true'
    if v is False:
        return 'false'
    return str(v)


class ParamRow(wx.Panel):
    """設定 1 つぶんの行: [書く] キー名 / 部品 / 既定値 / 1 行の説明。
    書くのチェックを外すと、部品は灰色で既定値を見せるだけ (= ファイルにキーを書かない)。"""

    def __init__(self, parent, spec, on_change, write_label='プロファイルに書く', strip_prefix=''):
        wx.Panel.__init__(self, parent)
        self.spec = spec
        self.on_change = on_change
        self.loading = False
        shown = spec['key'][len(strip_prefix):] if strip_prefix and spec['key'].startswith(strip_prefix) else spec['key']
        self.chk = wx.CheckBox(self, label=write_label)
        title = _bold(wx.StaticText(self, label='{}   {}'.format(shown, spec['title'])))
        self.ctrl = self._make_ctrl(spec)
        self.nullchk = None
        if spec['kind'] == 'floatnull':
            self.nullchk = wx.CheckBox(self, label='数値を使う (外すと null)')
        self.state = _gray(wx.StaticText(self, label=''))
        help_st = _gray(wx.StaticText(self, label=spec['help']))
        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(self.chk, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        top.Add(title, 0, wx.ALIGN_CENTER_VERTICAL)
        mid = wx.BoxSizer(wx.HORIZONTAL)
        mid.AddSpacer(24)
        if self.nullchk is not None:
            mid.Add(self.nullchk, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        mid.Add(self.ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        mid.Add(self.state, 0, wx.ALIGN_CENTER_VERTICAL)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(top, 0, wx.TOP, 4)
        v.Add(mid, 0, wx.TOP, 2)
        v.Add(help_st, 0, wx.LEFT | wx.TOP, 24)
        self.SetSizer(v)
        self.chk.Bind(wx.EVT_CHECKBOX, self._on_event)
        if self.nullchk is not None:
            self.nullchk.Bind(wx.EVT_CHECKBOX, self._on_event)
        kind = spec['kind']
        if kind == 'choice':
            self.ctrl.Bind(wx.EVT_CHOICE, self._on_event)
        elif kind == 'bool':
            self.ctrl.Bind(wx.EVT_CHECKBOX, self._on_event)
        elif kind == 'int':
            self.ctrl.Bind(wx.EVT_SPINCTRL, self._on_event)
            self.ctrl.Bind(wx.EVT_TEXT, self._on_event)
        else:
            self.ctrl.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_event)
            self.ctrl.Bind(wx.EVT_TEXT, self._on_event)

    def _make_ctrl(self, spec):
        kind = spec['kind']
        if kind == 'choice':
            return wx.Choice(self, choices=list(spec['choices']))
        if kind == 'bool':
            return wx.CheckBox(self, label='true')
        if kind == 'int':
            return wx.SpinCtrl(self, min=int(spec['lo']), max=int(spec['hi']), initial=int(spec['default']), size=(120, -1))
        c = wx.SpinCtrlDouble(self, min=spec['lo'], max=spec['hi'], initial=0.0, inc=spec['step'], size=(130, -1))
        c.SetDigits(3)
        return c

    def get_value(self):
        kind = self.spec['kind']
        if kind == 'choice':
            i = self.ctrl.GetSelection()
            return self.ctrl.GetString(i) if i != wx.NOT_FOUND else self.spec['default']
        if kind == 'bool':
            return bool(self.ctrl.GetValue())
        if kind == 'int':
            return int(self.ctrl.GetValue())
        if kind == 'floatnull' and not self.nullchk.GetValue():
            return None
        return float(round(self.ctrl.GetValue(), 4))

    def set_value(self, v):
        kind = self.spec['kind']
        if kind == 'choice':
            i = self.ctrl.FindString(str(v))
            if i == wx.NOT_FOUND:
                raise ValueError(v)
            self.ctrl.SetSelection(i)
        elif kind == 'bool':
            if not isinstance(v, bool):
                raise ValueError(v)
            self.ctrl.SetValue(v)
        elif kind == 'int':
            if not _is_int(v):
                raise ValueError(v)
            self.ctrl.SetValue(v)
        else:
            if kind == 'floatnull':
                self.nullchk.SetValue(v is not None)
                if v is None:
                    self.ctrl.SetValue(0.0)
                    return
            if not _is_num(v):
                raise ValueError(v)
            self.ctrl.SetValue(float(v))

    def load(self, present, value):
        """ファイルの状態を出す。present = キーが書いてあるか。値が型に合わなければ既定値を見せる。"""
        self.loading = True
        try:
            ok = False
            if present:
                try:
                    self.set_value(value)
                    ok = True
                except Exception:
                    ok = False
            if not ok:
                self.set_value(self.spec['default'])
            self.chk.SetValue(bool(present))
            self._refresh()
        finally:
            self.loading = False

    def _refresh(self):
        on = self.chk.GetValue() and self.IsEnabled()
        self.ctrl.Enable(on)
        if self.nullchk is not None:
            self.nullchk.Enable(on)
            if self.spec['kind'] == 'floatnull':
                self.ctrl.Enable(on and self.nullchk.GetValue())
        d = _fmt_default(self.spec['default'])
        if self.chk.GetValue():
            self.state.SetLabel('既定値: {}'.format(d))
        else:
            self.state.SetLabel('(既定)  既定値: {}'.format(d))
        self.Layout()

    def set_active(self, flag):
        """行ごと使えなくする / 戻す。"""
        self.Enable(flag)
        self.chk.Enable(flag)
        self._refresh()

    def _on_event(self, event):
        event.Skip()
        if self.loading:
            return
        self._refresh()
        self.on_change(self)


# ------------------------------------------------------------------------------
# タブ 1: ログ
# ------------------------------------------------------------------------------
class LogTab(wx.Panel):
    def __init__(self, parent, frame, log_path=None):
        wx.Panel.__init__(self, parent)
        self.frame = frame
        self.tail = LogTail(log_path or LOG_PATH)
        self.log_path = log_path or LOG_PATH
        self.lines = []
        self.paused = False
        self.exists = None
        self.flt = ''

        self.txt = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP | wx.TE_RICH2)
        self.txt.SetFont(wx.Font(10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        self.hint = _gray(wx.StaticText(self, label='ジョイスティックを起動するとここにログが出ます'))
        self.filter_box = wx.TextCtrl(self, size=(200, -1))
        self.btn_pause = wx.ToggleButton(self, label='一時停止')
        self.btn_clear = wx.Button(self, label='消す')
        self.btn_open = wx.Button(self, label='フォルダを開く')

        bar = wx.BoxSizer(wx.HORIZONTAL)
        bar.Add(wx.StaticText(self, label='絞り込み:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        bar.Add(self.filter_box, 0, wx.RIGHT, 12)
        bar.Add(self.btn_pause, 0, wx.RIGHT, 6)
        bar.Add(self.btn_clear, 0, wx.RIGHT, 6)
        bar.Add(self.btn_open, 0, wx.RIGHT, 12)
        bar.Add(_gray(wx.StaticText(self, label='例: [Panel]  (表示だけ消します。ファイルは消えません)')), 0, wx.ALIGN_CENTER_VERTICAL)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(bar, 0, wx.ALL, 8)
        v.Add(self.hint, 0, wx.LEFT | wx.BOTTOM, 10)
        v.Add(self.txt, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.SetSizer(v)

        self.filter_box.Bind(wx.EVT_TEXT, self.on_filter)
        self.btn_pause.Bind(wx.EVT_TOGGLEBUTTON, self.on_pause)
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear)
        self.btn_open.Bind(wx.EVT_BUTTON, self.on_open)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
        self.timer.Start(LOG_POLL_MS)

    def stop(self):
        try:
            self.timer.Stop()
        except Exception:
            pass

    def add_note(self, text):
        """この窓からの 1 行を、ログの表示に足す (ファイルには書かない)。"""
        try:
            line = '[VC-GUI] ' + text
            self.lines.append(line)
            if not self.paused and (not self.flt or self.flt.lower() in line.lower()):
                self.txt.AppendText(line + '\n')
                self.txt.ShowPosition(self.txt.GetLastPosition())
        except Exception:
            pass

    def _visible_lines(self, lines):
        if not self.flt:
            return lines
        f = self.flt.lower()
        return [l for l in lines if f in l.lower()]

    def refresh_view(self):
        shown = self._visible_lines(self.lines)
        self.txt.SetValue('\n'.join(shown) + ('\n' if shown else ''))
        self.txt.ShowPosition(self.txt.GetLastPosition())

    def on_timer(self, event):
        try:
            exists, reset, new_lines = self.tail.poll()
        except Exception as e:
            self.frame.set_status('ログを読めません: {}'.format(e))
            return
        if exists != self.exists:
            self.exists = exists
            self.hint.Show(not exists)
            self.Layout()
        if reset:
            self.lines = []
            if not self.paused:
                self.refresh_view()
            self.frame.set_status('ログが空になりました (ジョイスティックの起動)。先頭から読み直します')
        if not new_lines:
            return
        self.lines.extend(new_lines)
        over = len(self.lines) > LOG_MAX_LINES + 200
        if over:
            self.lines = self.lines[-LOG_MAX_LINES:]
        if self.paused:
            return
        if over:
            self.refresh_view()
            return
        shown = self._visible_lines(new_lines)
        if shown:
            self.txt.AppendText('\n'.join(shown) + '\n')
            self.txt.ShowPosition(self.txt.GetLastPosition())

    def on_filter(self, event):
        self.flt = self.filter_box.GetValue().strip()
        if not self.paused:
            self.refresh_view()

    def on_pause(self, event):
        self.paused = self.btn_pause.GetValue()
        self.btn_pause.SetLabel('再開' if self.paused else '一時停止')
        if not self.paused:
            self.refresh_view()
        self.frame.set_status('ログの表示を止めています (裏では読み続けます)' if self.paused else 'ログの表示を再開しました')

    def on_clear(self, event):
        self.lines = []
        self.txt.SetValue('')
        self.frame.set_status('表示を消しました (ファイルは消えていません)')

    def on_open(self, event):
        folder = os.path.dirname(self.log_path)
        try:
            if sys.platform == 'win32':
                os.startfile(folder)
            else:
                self.frame.set_status('フォルダを開けるのは Windows だけです: {}'.format(folder))
        except Exception as e:
            self.frame.set_status('フォルダを開けません: {}'.format(e))


# ------------------------------------------------------------------------------
# タブ 2: 設定 (古い configurator.py と同じ項目。PadConfig 経由)
# ------------------------------------------------------------------------------
CONFIG_ITEMS = [
    # (PadConfig の属性名, 種類, 英語の元の文, 日本語)
    ('trigger_pre_press_button', 'bool', 'Triggers pre press button', 'トリガーを軽く押したときのボタン'),
    ('trigger_press_button', 'bool', 'Triggers press button', 'トリガーを引き切ったときのボタン'),
    ('multibutton_trackpad', 'bool', '5 Button touchpad', 'タッチパッドを 5 つのボタンにする'),
    ('multibutton_trackpad_center_haptic', 'bool', 'Haptic feedback for trackpad button zones', 'タッチパッドの区画で振動させる'),
    ('touchpad_always_updates', 'bool', 'Touchpad mapping to axis while untouched (axis move to center when released)',
     '触っていないときも軸に出す (離すと軸が中央に戻る)'),
    ('vertical_wheel', 'bool', 'Steering wheel is vertical', 'ハンドルを縦に置く'),
    ('joystick_updates_only_when_grabbed', 'bool', 'Joystick moves only when grabbed (by right grip)', 'つかんでいる間だけスティックが動く (右グリップ)'),
    ('joystick_grabbing_switch', 'bool', 'Joystick grab is a switch', 'つかむ操作をスイッチにする'),
    ('edit_mode', 'bool', 'Layout edit mode', '配置の編集モード'),
    ('wheel_grabbed_by_grip', 'bool', 'Manual wheel grabbing', 'ハンドルを手でつかむ'),
    ('wheel_grabbed_by_grip_toggle', 'bool', 'Continuous (index, checked) or toggle (vive) wheel gripping',
     '握り続ける (index、チェックあり) / 切り替え (vive)'),
    ('wheel_show_wheel', 'bool', 'Show Wheel Overlay', 'ハンドルのオーバーレイを出す'),
    ('wheel_show_hands', 'bool', 'Show Hands Overlay', '手のオーバーレイを出す'),
    ('wheel_degrees', 'int', 'Wheel Degrees', 'ハンドルの回る角度 (度)'),
    ('wheel_centerforce', 'int', 'Center Force', '中央に戻す力'),
]
CONFIG_INT_MAX = {'wheel_degrees': 10000, 'wheel_centerforce': 100}


class ConfigTab(wx.Panel):
    def __init__(self, parent, frame):
        wx.Panel.__init__(self, parent)
        self.frame = frame
        self.config = None
        self.ctrls = collections.OrderedDict()
        self.loading = False
        v = wx.BoxSizer(wx.VERTICAL)
        self.msg = _gray(wx.StaticText(self, label=''))
        v.Add(self.msg, 0, wx.ALL, 8)
        box = wx.StaticBox(self, label='古い設定 (media/config.json、変えるとすぐ保存)')
        bs = wx.StaticBoxSizer(box, wx.VERTICAL)
        for key, kind, en, jp in CONFIG_ITEMS:
            if kind == 'bool':
                c = wx.CheckBox(self, label='{}   [{}]'.format(jp, en))
                c.Bind(wx.EVT_CHECKBOX, lambda e, k=key: self.on_change(k))
                bs.Add(c, 0, wx.ALL, 3)
            else:
                c = wx.SpinCtrl(self, min=0, max=CONFIG_INT_MAX.get(key, 100), size=(120, -1))
                c.Bind(wx.EVT_SPINCTRL, lambda e, k=key: self.on_change(k))
                c.Bind(wx.EVT_TEXT_ENTER, lambda e, k=key: self.on_change(k))
                row = wx.BoxSizer(wx.HORIZONTAL)
                row.Add(c, 0, wx.RIGHT, 8)
                row.Add(wx.StaticText(self, label='{}   [{}]'.format(jp, en)), 0, wx.ALIGN_CENTER_VERTICAL)
                bs.Add(row, 0, wx.ALL, 3)
            self.ctrls[key] = c
        v.Add(bs, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        self.btn_reload = wx.Button(self, label='設定を読み直す')
        self.btn_reload.Bind(wx.EVT_BUTTON, lambda e: self.read_config(ask=False))
        v.Add(self.btn_reload, 0, wx.ALL, 8)
        self.SetSizer(v)
        self.read_config(ask=True)

    def _set_enabled(self, flag):
        for c in self.ctrls.values():
            c.Enable(flag)

    def read_config(self, ask=True):
        """PadConfig を作って値を出す。壊れていたら古い configurator と同じく、既定値で作り直すかを聞く。"""
        if self.config is None:
            try:
                from steam_vr_wheel import PadConfig, ConfigException
            except Exception as e:
                self.msg.SetLabel('steam_vr_wheel を読み込めません: {}'.format(e))
                self._set_enabled(False)
                return
            try:
                self.config = PadConfig()
            except ConfigException as e:
                if not ask:
                    self.msg.SetLabel('設定ファイルのエラー: {}'.format(e))
                    self._set_enabled(False)
                    return
                msg = '設定ファイルのエラー: {}\n既定値で作り直しますか?'.format(e)
                if wx.MessageBox(msg, 'Config Error', wx.YES_NO | wx.ICON_QUESTION) == wx.YES:
                    try:
                        self.config = PadConfig(load_defaults=True)
                    except Exception as e2:
                        self.msg.SetLabel('既定値で作り直せません: {}'.format(e2))
                        self._set_enabled(False)
                        return
                else:
                    self.msg.SetLabel('設定ファイルを読めないので、この画面は使えません')
                    self._set_enabled(False)
                    return
            except Exception as e:
                self.msg.SetLabel('設定を読めません: {}'.format(e))
                self._set_enabled(False)
                return
        self.msg.SetLabel('')
        self._set_enabled(True)
        self.loading = True
        try:
            for key, c in self.ctrls.items():
                try:
                    c.SetValue(getattr(self.config, key))
                except Exception as e:
                    self.frame.set_status('設定 {} を読めません: {}'.format(key, e))
        finally:
            self.loading = False

    def on_change(self, key):
        if self.loading or self.config is None:
            return
        try:
            setattr(self.config, key, self.ctrls[key].GetValue())
            self.frame.set_status('設定を保存しました: {}'.format(key))
        except Exception as e:
            self.frame.set_status('設定を保存できません: {}: {}'.format(key, e))


# ------------------------------------------------------------------------------
# タブ 3: プロファイル (settings)
# ------------------------------------------------------------------------------
class SettingsTab(wx.Panel):
    def __init__(self, parent, frame):
        wx.Panel.__init__(self, parent)
        self.frame = frame
        self.model = frame.model
        self.rows = []
        sc = wx.ScrolledWindow(self)
        sc.SetScrollRate(0, 12)
        v = wx.BoxSizer(wx.VERTICAL)
        self.name_st = _bold(wx.StaticText(sc, label=''))
        v.Add(self.name_st, 0, wx.ALL, 8)
        v.Add(_gray(wx.StaticText(sc, label='「プロファイルに書く」を外したキーはファイルに書かず、コードの既定 (下の既定値) で動きます。')), 0, wx.LEFT | wx.BOTTOM, 8)
        for spec in SETTING_SPECS:
            row = ParamRow(sc, spec, self.on_row_change)
            self.rows.append(row)
            v.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
            v.Add(wx.StaticLine(sc), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 8)
        v.Add(_bold(wx.StaticText(sc, label='その他の設定 (読むだけ。そのまま保存されます)')), 0, wx.ALL, 8)
        self.extra = wx.TextCtrl(sc, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_DONTWRAP, size=(-1, 120))
        v.Add(self.extra, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        sc.SetSizer(v)
        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(sc, 1, wx.EXPAND)
        self.SetSizer(outer)
        self.sc = sc

    def on_model_loaded(self):
        settings = self.model.settings()
        prof = self.model.data.get('profile')
        name = prof.get('name') if isinstance(prof, dict) else None
        self.name_st.SetLabel('プロファイル: {}'.format(name or os.path.basename(self.model.path or '')))
        usable = settings is not None or self.model.data.get('settings') is None
        for row in self.rows:
            key = row.spec['key']
            present = bool(settings) and key in settings
            row.load(present, settings[key] if present else None)
            row.set_active(usable)
        extra_lines = []
        if settings:
            for k in settings:
                if k not in SETTING_KEYS:
                    extra_lines.append('{} = {}'.format(k, json.dumps(settings[k], ensure_ascii=False)))
        if not usable:
            extra_lines.append('settings が { } の形ではないので、ここでは編集できません')
        self.extra.SetValue('\n'.join(extra_lines) if extra_lines else '(なし)')
        self.sc.Layout()
        self.sc.FitInside()

    def on_row_change(self, row):
        key = row.spec['key']
        settings = self.model.settings(create=True)
        if settings is None:
            return
        if row.chk.GetValue():
            settings[key] = row.get_value()
        elif key in settings:
            del settings[key]
        self.frame.mark_dirty()


# ------------------------------------------------------------------------------
# パネルの見本 (丸いメニュー)
# ------------------------------------------------------------------------------
class PreviewPanel(wx.Panel):
    COLORS = {
        'item': (70, 110, 170), 'folder': (60, 140, 140), 'none': (95, 95, 95), 'rest': (120, 120, 120),
        'missing': (200, 40, 190), 'back': (70, 140, 80),
    }

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, size=(PREVIEW_SIZE, PREVIEW_SIZE))
        self.SetMinSize((PREVIEW_SIZE, PREVIEW_SIZE))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.entries = []
        self.caption = ''
        self.highlight = None       # 光らせるスロットの添字 (0 始まり。無ければ None)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, lambda e: (self.Refresh(), e.Skip()))

    def set_level(self, entries, caption='', highlight=None):
        self.entries = entries
        self.caption = caption
        self.highlight = highlight
        self.Refresh()

    def on_paint(self, event):
        import math
        dc = wx.AutoBufferedPaintDC(self)
        dc.SetBackground(wx.Brush(wx.Colour(30, 32, 36)))
        dc.Clear()
        gc = wx.GraphicsContext.Create(dc)
        if gc is None:
            return
        w, h = self.GetClientSize()
        cx, cy = w / 2.0, h / 2.0 + 6
        big = min(w, h / 1.0) / 2.0 - 14
        small = big * 0.26
        gc.SetFont(wx.Font(8, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL), wx.Colour(235, 235, 235))
        gc.DrawText(self.caption, 6, 3)
        n = len(self.entries)
        if n == 0:
            gc.DrawText('(スロットがありません)', cx - 50, cy)
            return

        def pt(a, r):
            return cx + r * math.sin(a), cy - r * math.cos(a)

        steps = 12
        hl_path = None
        for i, (text, kind) in enumerate(self.entries):
            a0 = (i - 0.5) * 2 * math.pi / n
            a1 = (i + 0.5) * 2 * math.pi / n
            path = gc.CreatePath()
            x, y = pt(a0, big)
            path.MoveToPoint(x, y)
            for s in range(1, steps + 1):
                x, y = pt(a0 + (a1 - a0) * s / float(steps), big)
                path.AddLineToPoint(x, y)
            for s in range(steps, -1, -1):
                x, y = pt(a0 + (a1 - a0) * s / float(steps), small)
                path.AddLineToPoint(x, y)
            path.CloseSubpath()
            gc.SetBrush(wx.Brush(wx.Colour(*self.COLORS.get(kind, (70, 110, 170)))))
            gc.SetPen(wx.Pen(wx.Colour(20, 20, 24), 2))
            gc.DrawPath(path)
            if i == self.highlight:
                hl_path = path
            label = '{} {}'.format(i + 1, text)
            if len(label) > 11:
                label = label[:10] + '..'
            tw, th = gc.GetTextExtent(label)[:2]
            mx, my = pt((a0 + a1) / 2.0, (big + small) / 2.0)
            gc.DrawText(label, mx - tw / 2.0, my - th / 2.0)
        gc.SetBrush(wx.Brush(wx.Colour(30, 32, 36)))
        gc.SetPen(wx.Pen(wx.Colour(20, 20, 24), 2))
        gc.DrawEllipse(cx - small, cy - small, small * 2, small * 2)
        if hl_path is not None:     # 編集中のスロットは、黄色の太い縁で囲む
            gc.SetPen(wx.Pen(wx.Colour(255, 215, 0), 4))
            gc.StrokePath(hl_path)


# ------------------------------------------------------------------------------
# タブ 0: コクピット (動いている本体の操作)
# ------------------------------------------------------------------------------
class CockpitTab(wx.Panel):
    def __init__(self, parent, frame):
        wx.Panel.__init__(self, parent)
        self.frame = frame
        self.shown_profiles = None      # 選び欄に今入れている一覧 (変わったときだけ作り直す)
        self.shown_file = None
        self.ctrls = []                 # 止まっているときに無効にする部品

        self.info = _bold(wx.StaticText(self, label=''))
        self.ch = wx.Choice(self, size=(260, -1))
        self.btn_switch = wx.Button(self, label='切り替え')
        self.btn_reload = wx.Button(self, label='読み直し')
        self.btn_show = wx.Button(self, label='コンソールを出す')
        self.btn_hide = wx.Button(self, label='コンソールを隠す')
        self.dbg_btns = []
        for name, text in DEBUG_COMMANDS:
            b = wx.Button(self, label=text)
            b.dbg_name = name
            self.dbg_btns.append(b)
        self.ctrls = [self.ch, self.btn_switch, self.btn_reload, self.btn_show, self.btn_hide] + self.dbg_btns

        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(self.info, 0, wx.ALL, 10)
        v.Add(_bold(wx.StaticText(self, label='動かしているプロファイル')), 0, wx.LEFT | wx.TOP, 10)
        row = wx.BoxSizer(wx.HORIZONTAL)
        row.Add(self.ch, 0, wx.RIGHT, 6)
        row.Add(self.btn_switch, 0, wx.RIGHT, 6)
        row.Add(self.btn_reload, 0)
        v.Add(row, 0, wx.ALL, 10)
        v.Add(_gray(wx.StaticText(self, label='切り替え = 選んだプロファイルを読み込ませる。読み直し = 今のプロファイルをファイルから読み直させる。')), 0, wx.LEFT, 10)
        v.Add(_bold(wx.StaticText(self, label='黒いコンソール窓')), 0, wx.LEFT | wx.TOP, 18)
        row2 = wx.BoxSizer(wx.HORIZONTAL)
        row2.Add(self.btn_show, 0, wx.RIGHT, 6)
        row2.Add(self.btn_hide, 0)
        v.Add(row2, 0, wx.ALL, 10)
        v.Add(_gray(wx.StaticText(self, label='この窓が開いている間、本体は黒いコンソール窓を隠します。')), 0, wx.LEFT, 10)
        v.Add(_bold(wx.StaticText(self, label='デバッグ (結果は ログ のタブに出ます)')), 0, wx.LEFT | wx.TOP, 18)
        row3 = wx.BoxSizer(wx.HORIZONTAL)
        for b in self.dbg_btns:
            row3.Add(b, 0, wx.RIGHT, 6)
        v.Add(row3, 0, wx.ALL, 10)
        self.SetSizer(v)

        self.btn_switch.Bind(wx.EVT_BUTTON, self.on_switch)
        self.btn_reload.Bind(wx.EVT_BUTTON, lambda e: self.frame.send_cmd({'cmd': 'profile_reload'}))
        self.btn_show.Bind(wx.EVT_BUTTON, lambda e: self.frame.send_cmd({'cmd': 'console', 'show': True}))
        self.btn_hide.Bind(wx.EVT_BUTTON, lambda e: self.frame.send_cmd({'cmd': 'console', 'show': False}))
        for b in self.dbg_btns:
            b.Bind(wx.EVT_BUTTON, self.on_debug)
        self.update_status(None)

    def update_status(self, st):
        """status (動いていれば dict、止まっていれば None) を画面に反映する。1 秒ごとに呼ばれる。"""
        running = st is not None
        for c in self.ctrls:
            try:
                c.Enable(running)
            except Exception:
                pass
        if not running:
            self.info.SetLabel('コクピットは止まっています (ボタンは使えません)')
            return
        self.info.SetLabel(cockpit_summary(st))
        profiles = st.get('profiles')
        profiles = [str(p) for p in profiles] if isinstance(profiles, list) else []
        cur = st.get('profile_file')
        if profiles != self.shown_profiles or cur != self.shown_file:
            # 一覧か今のプロファイルが変わったときだけ選び直す (選んでいる最中の選択を壊さない)
            self.shown_profiles = profiles
            self.shown_file = cur
            self.ch.Clear()
            for p in profiles:
                self.ch.Append(p)
            if cur in profiles:
                self.ch.SetSelection(profiles.index(cur))

    def on_switch(self, event):
        i = self.ch.GetSelection()
        if i == wx.NOT_FOUND:
            self.frame.set_status('切り替えるプロファイルを選んでください')
            return
        self.frame.send_cmd({'cmd': 'profile_load', 'file': self.ch.GetString(i)})

    def on_debug(self, event):
        self.frame.send_cmd({'cmd': 'debug', 'name': event.GetEventObject().dbg_name})


def cockpit_summary(st):
    """状態の 1 行 (窓の上の帯と、コクピットのタブで使う)。st が None なら止まっている。"""
    if st is None:
        return 'コクピット: 止まっている'
    name = st.get('profile_name')
    fname = st.get('profile_file')
    text = 'コクピット: 動作中 v{} / プロファイル: {} ({})'.format(
        st.get('app_version', '?'), name if name else '-', fname if fname else 'ファイルなし')
    if st.get('config_mode'):
        text += ' / コンフィグ中'
    return text


class CloseChoiceDialog(wx.Dialog):
    """閉じるときの 3 択。choice = 'quit' / 'close' / 'cancel'。"""

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent, title='閉じる')
        self.choice = 'cancel'
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(wx.StaticText(self, label='コクピットが動いています。どうしますか?'), 0, wx.ALL, 14)
        h = wx.BoxSizer(wx.HORIZONTAL)
        for key, text in (('quit', 'コクピットも終了する'), ('close', 'この窓だけ閉じる'), ('cancel', 'キャンセル')):
            b = wx.Button(self, label=text)
            b.choice_key = key
            b.Bind(wx.EVT_BUTTON, self.on_btn)
            h.Add(b, 0, wx.RIGHT, 8)
            if key == 'cancel':
                b.SetDefault()
        v.Add(h, 0, wx.ALL, 14)
        v.Add(_gray(wx.StaticText(self, label='「この窓だけ閉じる」を選ぶと、本体は黒いコンソール窓をまた出します。')), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)
        self.SetSizerAndFit(v)
        self.CentreOnParent()

    def on_btn(self, event):
        self.choice = event.GetEventObject().choice_key
        self.EndModal(wx.ID_OK if self.choice != 'cancel' else wx.ID_CANCEL)


def ask_close_choice(parent):
    dlg = CloseChoiceDialog(parent)
    try:
        dlg.ShowModal()
        return dlg.choice       # X で閉じたときは 'cancel' のまま
    finally:
        dlg.Destroy()


# ------------------------------------------------------------------------------
# タブ 4: パネル
# ------------------------------------------------------------------------------
KIND_ITEM, KIND_FOLDER, KIND_NONE, KIND_REST, KIND_EMPTY = '項目', 'フォルダ', 'NONE', 'REST', '空'


class PanelTab(wx.Panel):
    def __init__(self, parent, frame):
        wx.Panel.__init__(self, parent)
        self.frame = frame
        self.model = frame.model
        self.cur = None            # 選んでいる木の印 (タプル)
        self.cur_item = None       # 選んでいる項目の dict (空きなら None)
        self.loading = False
        self.rebuilding = False
        self.node_of = {}
        self.brake_rows = []
        self.left_fname = None     # 左の見本に出している階層 (右を選んでいる間も覚えておく)
        self._build()

    # ---- 画面の組み立て ----
    def _build(self):
        self.tree = wx.TreeCtrl(self, size=(290, -1), style=wx.TR_HAS_BUTTONS | wx.TR_HIDE_ROOT | wx.TR_SINGLE)
        self.btn_add = wx.Button(self, label='スロットを足す')
        self.btn_del = wx.Button(self, label='消す')
        self.btn_folder = wx.Button(self, label='フォルダを足す')
        self.btn_up = wx.Button(self, label='上へ')
        self.btn_down = wx.Button(self, label='下へ')
        grid = wx.FlexGridSizer(3, 2, 4, 4)
        for b in (self.btn_add, self.btn_del, self.btn_folder, self.btn_up, self.btn_down):
            grid.Add(b, 0, wx.EXPAND)
        left = wx.BoxSizer(wx.VERTICAL)
        left.Add(self.tree, 1, wx.EXPAND | wx.BOTTOM, 6)
        left.Add(grid, 0, wx.EXPAND)

        self.form = wx.ScrolledWindow(self)
        self.form.SetScrollRate(0, 12)
        fv = wx.BoxSizer(wx.VERTICAL)
        self.info = _gray(wx.StaticText(self.form, label='左の木からスロットかフォルダを選んでください。'))
        fv.Add(self.info, 0, wx.ALL, 8)
        self.box_folder = self._build_folder_box(self.form)
        fv.Add(self.box_folder, 0, wx.EXPAND | wx.ALL, 4)
        self.box_slot = self._build_slot_box(self.form)
        fv.Add(self.box_slot, 0, wx.EXPAND | wx.ALL, 4)
        self.form.SetSizer(fv)

        self.preview_l = PreviewPanel(self)
        self.preview_r = PreviewPanel(self)
        pair = wx.BoxSizer(wx.HORIZONTAL)
        pair.Add(self.preview_l, 0, wx.RIGHT, 6)
        pair.Add(self.preview_r, 0)
        right = wx.BoxSizer(wx.VERTICAL)
        right.Add(pair, 0)
        right.Add(_gray(wx.StaticText(self, label='見本: 左パネル (今の階層) と右パネルを並べて出します。1 番が上、時計回り。\n黄色の縁 = 編集中の項目、灰 = NONE/REST、赤紫 = 書いていない番号、緑 = 戻る')), 0, wx.TOP, 6)

        top = wx.BoxSizer(wx.HORIZONTAL)
        top.Add(left, 0, wx.EXPAND | wx.ALL, 6)
        top.Add(self.form, 1, wx.EXPAND | wx.TOP | wx.BOTTOM, 6)
        top.Add(right, 0, wx.ALL, 6)

        self.val = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 140))
        self.val.InsertColumn(0, '種類', width=60)
        self.val.InsertColumn(1, '場所', width=170)
        self.val.InsertColumn(2, '内容', width=800)
        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(top, 1, wx.EXPAND)
        v.Add(_bold(wx.StaticText(self, label='警告の一覧 (変えるたびに作り直します)')), 0, wx.LEFT, 8)
        v.Add(self.val, 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(v)

        self.tree.Bind(wx.EVT_TREE_SEL_CHANGED, self.on_tree_sel)
        self.btn_add.Bind(wx.EVT_BUTTON, self.on_add_slot)
        self.btn_del.Bind(wx.EVT_BUTTON, self.on_delete)
        self.btn_folder.Bind(wx.EVT_BUTTON, self.on_add_folder)
        self.btn_up.Bind(wx.EVT_BUTTON, lambda e: self.on_move(-1))
        self.btn_down.Bind(wx.EVT_BUTTON, lambda e: self.on_move(1))

    def _mk_row(self, parent, text, make_ctrl, expand=False):
        p = wx.Panel(parent)
        s = wx.BoxSizer(wx.HORIZONTAL)
        st = wx.StaticText(p, label=text, size=(120, -1))
        ctrl = make_ctrl(p)
        s.Add(st, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        s.Add(ctrl, 1 if expand else 0, wx.ALIGN_CENTER_VERTICAL)
        p.SetSizer(s)
        return p, ctrl

    def _build_folder_box(self, parent):
        p = wx.Panel(parent)
        v = wx.BoxSizer(wx.VERTICAL)
        self.folder_title = _bold(wx.StaticText(p, label=''))
        v.Add(self.folder_title, 0, wx.ALL, 4)
        self.txt_fname = wx.TextCtrl(p, size=(220, -1), style=wx.TE_PROCESS_ENTER)
        self.btn_rename = wx.Button(p, label='名前を変える')
        self.btn_root = wx.Button(p, label='ルートにする')
        r = wx.BoxSizer(wx.HORIZONTAL)
        r.Add(self.txt_fname, 0, wx.RIGHT, 6)
        r.Add(self.btn_rename, 0, wx.RIGHT, 6)
        r.Add(self.btn_root, 0)
        v.Add(r, 0, wx.ALL, 4)
        v.Add(_gray(wx.StaticText(p, label='名前を変えると、指している項目の folder も書き換えます。')), 0, wx.ALL, 4)
        p.SetSizer(v)
        self.btn_rename.Bind(wx.EVT_BUTTON, self.on_rename)
        self.txt_fname.Bind(wx.EVT_TEXT_ENTER, self.on_rename)
        self.btn_root.Bind(wx.EVT_BUTTON, self.on_make_root)
        return p

    def _build_slot_box(self, parent):
        p = wx.Panel(parent)
        v = wx.BoxSizer(wx.VERTICAL)
        self.slot_title = _bold(wx.StaticText(p, label=''))
        v.Add(self.slot_title, 0, wx.ALL, 4)

        self.row_kind, self.ch_kind = self._mk_row(p, '種類', lambda q: wx.Choice(q, choices=[KIND_ITEM]))
        self.row_label, self.txt_label = self._mk_row(p, 'ラベル', lambda q: wx.TextCtrl(q, size=(260, -1)))
        self.lbl_hint = _gray(wx.StaticText(p, label=''))
        self.row_folder, self.ch_folder = self._mk_row(p, '入るフォルダ', lambda q: wx.Choice(q, choices=['']))
        self.row_cmd, self.ch_cmd = self._mk_row(
            p, '命令 (command)', lambda q: wx.Choice(q, choices=['(なし)'] + PANEL_COMMANDS))
        for r in (self.row_kind, self.row_label):
            v.Add(r, 0, wx.EXPAND | wx.ALL, 2)
        v.Add(self.lbl_hint, 0, wx.LEFT, 130)
        v.Add(self.row_folder, 0, wx.EXPAND | wx.ALL, 2)
        v.Add(self.row_cmd, 0, wx.EXPAND | wx.ALL, 2)

        # args: vjoy_button
        self.pnl_vjoy, self.txt_buttons = self._mk_row(p, 'ボタン番号', lambda q: wx.TextCtrl(q, size=(160, -1)))
        vj = wx.BoxSizer(wx.VERTICAL)
        vj.Add(self.pnl_vjoy, 0, wx.EXPAND | wx.ALL, 2)
        self.lbl_vjoy = _gray(wx.StaticText(p, label='1〜128。同時押しはカンマで区切る (例 3,5)。1 つなら {"button": N}、複数なら {"buttons": [..]}。'))
        v.Add(vj, 0, wx.EXPAND)
        v.Add(self.lbl_vjoy, 0, wx.LEFT, 130)
        # args: brake
        self.pnl_brake = wx.Panel(p)
        bv = wx.BoxSizer(wx.VERTICAL)
        bv.Add(_gray(wx.StaticText(self.pnl_brake, label='brake の上書き (外した項目は、プロファイルの settings の brake.* を使う)')), 0, wx.ALL, 2)
        for spec in BRAKE_ARG_SPECS:
            row = ParamRow(self.pnl_brake, spec, self.on_brake_row, write_label='上書きする', strip_prefix='brake.')
            self.brake_rows.append(row)
            bv.Add(row, 0, wx.EXPAND)
        self.pnl_brake.SetSizer(bv)
        v.Add(self.pnl_brake, 0, wx.EXPAND | wx.LEFT, 10)
        # args: cruise
        self.pnl_cruise, self.ch_action = self._mk_row(
            p, 'cruise の動き', lambda q: wx.Choice(q, choices=['(既定: toggle)'] + CRUISE_ACTIONS))
        v.Add(self.pnl_cruise, 0, wx.EXPAND | wx.ALL, 2)
        self.lbl_cruise = _gray(wx.StaticText(p, label='toggle = トリガーの二度引きが要る。on / off / center = トリガー 1 回で実行。'))
        v.Add(self.lbl_cruise, 0, wx.LEFT, 130)

        self.row_exec, self.ch_exec = self._mk_row(p, '実行 (exec)', lambda q: wx.Choice(q, choices=['(既定: tilt)', 'tilt', 'trigger']))
        self.row_hold, self.ch_hold = self._mk_row(p, '押しっぱなし (hold)', lambda q: wx.Choice(q, choices=['(既定)', 'true', 'false']))
        self.row_blocka, self.ch_blocka = self._mk_row(p, 'A を封じる (block_a)', lambda q: wx.Choice(q, choices=['(既定)', 'true', 'false']))
        self.row_latch, self.ch_latch = self._mk_row(p, '選びが残る (latch)', lambda q: wx.Choice(q, choices=['(既定)', 'true', 'false']))
        self.row_hud, self.ch_hud = self._mk_row(p, 'HUD の印 (hud)', lambda q: wx.Choice(q, choices=['(なし)'] + HUD_MARKS))
        for r in (self.row_exec, self.row_hold, self.row_blocka, self.row_latch, self.row_hud):
            v.Add(r, 0, wx.EXPAND | wx.ALL, 2)
        self.lbl_misc = _gray(wx.StaticText(
            p, label='exec = 右パネルだけ (tilt はスティックを倒す、trigger はトリガー)。hold = 操作が続く間ボタンを押し続ける。\n'
                     'block_a = 選んでいる間、A ボタンをゲームへ出さない。hud = 押している間、その HUD の印を光らせる。\n'
                     'latch = false にすると、スティックを中央に戻したとき選びが消えて、前に選んでいた項目に戻る (右の TGT など)。'))
        v.Add(self.lbl_misc, 0, wx.LEFT | wx.TOP, 6)
        p.SetSizer(v)

        self.ch_kind.Bind(wx.EVT_CHOICE, self.on_kind)
        self.txt_label.Bind(wx.EVT_TEXT, self.on_form)
        self.ch_folder.Bind(wx.EVT_CHOICE, self.on_form)
        self.ch_cmd.Bind(wx.EVT_CHOICE, self.on_command)
        self.txt_buttons.Bind(wx.EVT_TEXT, self.on_form)
        self.ch_action.Bind(wx.EVT_CHOICE, self.on_form)
        for c in (self.ch_exec, self.ch_hold, self.ch_blocka, self.ch_latch, self.ch_hud):
            c.Bind(wx.EVT_CHOICE, self.on_form)
        return p

    # ---- モデルが読み込まれたとき ----
    def on_model_loaded(self):
        self.cur = None
        self.cur_item = None
        self.rebuild_tree(None)
        self.refresh_all_views()

    # ---- 木 ----
    def _slot_range(self, table, root):
        """木に出す番号を数字順で返す: (番号, 書いてあるか)。隙間は空きとして出す。下の階層は 2 から。"""
        start = 1 if root else 2
        written = [s for s in valid_slots(table, root)]
        top = max([int(s) for s in written] + [start - 1])
        return [(str(i), str(i) in written) for i in range(start, top + 1)]

    def _item_text(self, slot, row):
        label = str(row.get('label', ''))
        t = row.get('type')
        extra = ''
        if t in ('NONE', 'REST'):
            extra = '  [{}]'.format(t)
        elif row.get('folder') is not None:
            extra = '  → {}'.format(row.get('folder'))
        elif row.get('command'):
            extra = '  ({})'.format(row.get('command'))
        return '{}: {}{}'.format(slot, label, extra)

    def rebuild_tree(self, select):
        """木を作り直す。select = 選び直したい印。見つからなければ近い親を選ぶ。"""
        self.rebuilding = True
        try:
            self.tree.DeleteAllItems()
            self.node_of = {}
            root = self.tree.AddRoot('panels')
            data = self.model.data
            # 左
            lnode = self.tree.AppendItem(root, 'left_game  (左パネル)')
            self.tree.SetItemData(lnode, ('side', 'left'))
            self.node_of[('side', 'left')] = lnode
            folders = get_folders(data)
            rootname = panel_root_name(data)
            if folders:
                names = [rootname] if rootname in folders else []
                names += [n for n in folders if n != rootname]
                for fname in names:
                    key = ('folder', 'left', fname)
                    fnode = self.tree.AppendItem(lnode, '{}{}'.format(fname, '  (ルート)' if fname == rootname else ''))
                    self.tree.SetItemData(fnode, key)
                    self.node_of[key] = fnode
                    table = folders[fname]
                    if isinstance(table, dict):
                        self._add_slot_nodes(fnode, 'left', fname, table, fname == rootname)
            # 右
            rnode = self.tree.AppendItem(root, 'right_game  (右パネル)')
            self.tree.SetItemData(rnode, ('side', 'right'))
            self.node_of[('side', 'right')] = rnode
            rtable = get_table(data, 'right', 'items')
            if rtable is not None:
                self._add_slot_nodes(rnode, 'right', 'items', rtable, True)
            self.tree.ExpandAll()
        finally:
            self.rebuilding = False
        target = select if select in self.node_of else None
        if target is None and select is not None:
            if select[0] == 'slot':
                fk = ('folder', 'left', select[2]) if select[1] == 'left' else ('side', 'right')
                target = fk if fk in self.node_of else None
        if target is None:
            target = ('side', 'left')
        self.tree.SelectItem(self.node_of[target])
        self.on_selection(target)

    def _add_slot_nodes(self, parent, side, fname, table, root):
        if not root:
            key = ('back', side, fname)
            n = self.tree.AppendItem(parent, '1: (戻る・予約)')
            self.tree.SetItemData(n, key)
            self.tree.SetItemTextColour(n, wx.Colour(*GRAY))
        for slot, written in self._slot_range(table, root):
            key = ('slot', side, fname, slot)
            if written:
                n = self.tree.AppendItem(parent, self._item_text(slot, table[slot]))
            else:
                n = self.tree.AppendItem(parent, '{}: (空)'.format(slot))
                self.tree.SetItemTextColour(n, wx.Colour(200, 40, 190))
            self.tree.SetItemData(n, key)
            self.node_of[key] = n
        for slot in sorted(table.keys(), key=_slot_sort_key):
            if slot in [s for s, w in self._slot_range(table, root)]:
                continue
            key = ('slot', side, fname, slot)
            row = table[slot]
            text = self._item_text(slot, row) if isinstance(row, dict) else '{}: ?'.format(slot)
            n = self.tree.AppendItem(parent, '!' + text)
            self.tree.SetItemData(n, key)
            self.tree.SetItemTextColour(n, wx.Colour(*RED))
            self.node_of[key] = n

    def on_tree_sel(self, event):
        if self.rebuilding:
            return
        item = event.GetItem()
        if not item.IsOk():
            return
        self.on_selection(self.tree.GetItemData(item))

    def on_selection(self, key):
        self.cur = key
        self.cur_item = None
        if key is not None and key[0] == 'slot':
            table = get_table(self.model.data, key[1], key[2])
            row = table.get(key[3]) if table is not None else None
            self.cur_item = row if isinstance(row, dict) else None
        self.show_form()
        self.refresh_all_views()

    # ---- フォーム ----
    def show_form(self):
        key = self.cur
        self.loading = True
        try:
            kind = key[0] if key else None
            self.info.Show(kind not in ('folder', 'slot'))
            self.box_folder.Show(kind == 'folder')
            self.box_slot.Show(kind == 'slot')
            if kind == 'side':
                self.info.SetLabel('左パネル (left_game): フォルダを入れ子にできる。\n右パネル (right_game): 1 階層だけ。フォルダは書けません。'
                                   if key[1] == 'left' else
                                   '右パネル (right_game): 1 階層だけ。フォルダは書けません。\n「スロットを足す」で項目を足せます。')
            elif kind == 'back':
                self.info.SetLabel('1 番は下の階層の「戻る」に予約されています。ここには書けません。')
            elif key is None:
                self.info.SetLabel('左の木からスロットかフォルダを選んでください。')
            if kind == 'folder':
                rootname = panel_root_name(self.model.data)
                self.folder_title.SetLabel('フォルダ: {}{}'.format(key[2], '  (ルート)' if key[2] == rootname else ''))
                self.txt_fname.ChangeValue(key[2])
                self.btn_root.Enable(key[2] != rootname)
            if kind == 'slot':
                self.load_slot_form()
        finally:
            self.loading = False
        self.form.Layout()
        self.form.FitInside()

    def load_slot_form(self):
        _, side, fname, slot = self.cur
        item = self.cur_item
        is_left = side == 'left'
        self.slot_title.SetLabel('{} パネル / {} / スロット {}'.format('左' if is_left else '右', fname if is_left else '', slot).replace(' /  /', ' /'))
        kinds = [KIND_ITEM] + ([KIND_FOLDER] if is_left else []) + [KIND_NONE, KIND_REST, KIND_EMPTY]
        self.ch_kind.Clear()
        for k in kinds:
            self.ch_kind.Append(k)
        if item is None:
            kind = KIND_EMPTY
        elif item.get('type') == 'NONE':
            kind = KIND_NONE
        elif item.get('type') == 'REST':
            kind = KIND_REST
        elif item.get('folder') is not None and is_left:
            kind = KIND_FOLDER
        else:
            kind = KIND_ITEM
        self.ch_kind.SetSelection(kinds.index(kind))
        has = item is not None
        self.txt_label.ChangeValue(str(item.get('label', '')) if has else '')
        self.txt_label.Enable(has)
        self._update_label_hint()
        # フォルダ
        self.ch_folder.Clear()
        names = [n for n in (get_folders(self.model.data) or {})]
        for n in names:
            self.ch_folder.Append(str(n))
        if has and item.get('folder') is not None:
            i = self.ch_folder.FindString(str(item['folder']))
            if i == wx.NOT_FOUND:
                i = self.ch_folder.Append(str(item['folder']))
            self.ch_folder.SetSelection(i)
        show_folder = is_left and kind == KIND_FOLDER
        self.row_folder.Show(show_folder)
        # 命令
        show_cmd = has and kind == KIND_ITEM
        self.row_cmd.Show(show_cmd)
        cmd = item.get('command') if has else None
        self.ch_cmd.Clear()
        for c in ['(なし)'] + PANEL_COMMANDS:
            self.ch_cmd.Append(c)
        if cmd is None:
            self.ch_cmd.SetSelection(0)
        else:
            i = self.ch_cmd.FindString(str(cmd))
            if i == wx.NOT_FOUND:
                i = self.ch_cmd.Append(str(cmd))
            self.ch_cmd.SetSelection(i)
        args = item.get('args') if has and isinstance(item.get('args'), dict) else {}
        # args の部品
        self.pnl_vjoy.Show(show_cmd and cmd == 'vjoy_button')
        self.lbl_vjoy.Show(show_cmd and cmd == 'vjoy_button')
        self.pnl_brake.Show(show_cmd and cmd == 'brake')
        self.pnl_cruise.Show(show_cmd and cmd == 'cruise')
        self.lbl_cruise.Show(show_cmd and cmd == 'cruise')
        if isinstance(args.get('buttons'), list):
            self.txt_buttons.ChangeValue(','.join(str(b) for b in args['buttons']))
        elif 'button' in args:
            self.txt_buttons.ChangeValue(str(args['button']))
        else:
            self.txt_buttons.ChangeValue('')
        for row in self.brake_rows:
            k = row.spec['key'][len('brake.'):]
            row.load(k in args, args.get(k))
        act = args.get('action')
        i = self.ch_action.FindString(str(act)) if act is not None else 0
        self.ch_action.SetSelection(i if i != wx.NOT_FOUND else 0)
        # その他
        self.row_exec.Show(has and not is_left)
        self.row_hold.Show(has)
        self.row_blocka.Show(has)
        self.row_latch.Show(has)
        self.row_hud.Show(has)
        self.lbl_misc.Show(has)
        self._set_choice(self.ch_exec, item.get('exec') if has else None, ['tilt', 'trigger'], 1)
        self._set_tri(self.ch_hold, item.get('hold') if has else None)
        self._set_tri(self.ch_blocka, item.get('block_a') if has else None)
        self._set_tri(self.ch_latch, item.get('latch') if has else None)
        self._set_choice(self.ch_hud, item.get('hud') if has else None, HUD_MARKS, 1)
        self.box_slot.Layout()

    @staticmethod
    def _set_choice(ch, value, options, offset):
        if value is None:
            ch.SetSelection(0)
        elif value in options:
            ch.SetSelection(options.index(value) + offset)
        else:
            ch.SetSelection(0)

    @staticmethod
    def _set_tri(ch, value):
        ch.SetSelection(1 if value is True else (2 if value is False else 0))

    @staticmethod
    def _get_tri(ch):
        return (None, True, False)[ch.GetSelection()]

    def _update_label_hint(self):
        text = self.txt_label.GetValue()
        bad = sorted(set(c for c in text if c not in LABEL_OK_CHARS))
        self.lbl_hint.SetLabel('HUD の文字で出せない字: {}'.format(' '.join(bad)[:30]) if bad else
                               'HUD は英大文字・数字・空白 / . - + を出せます')

    # ---- フォームの変更 ----
    def on_kind(self, event):
        if self.loading or self.cur is None or self.cur[0] != 'slot':
            return
        _, side, fname, slot = self.cur
        kind = self.ch_kind.GetString(self.ch_kind.GetSelection())
        table = get_table(self.model.data, side, fname, create=True)
        if kind == KIND_EMPTY:
            if slot in table:
                del table[slot]
            self.model_changed(rebuild=True)
            return
        item = table.get(slot)
        if not isinstance(item, dict):
            item = collections.OrderedDict()
            item['label'] = NEW_ITEM_LABEL
            table[slot] = item
        if kind == KIND_FOLDER:
            others = [n for n in (get_folders(self.model.data) or {}) if n != fname]
            if not others:
                self.frame.set_status('入れるフォルダがありません。先に「フォルダを足す」を押してください')
                self.model_changed(rebuild=True)
                return
            item.pop('type', None)
            item['folder'] = others[0]
        elif kind in (KIND_NONE, KIND_REST):
            item.pop('folder', None)
            item['type'] = kind
        else:
            item.pop('folder', None)
            if item.get('type') in ('NONE', 'REST'):
                del item['type']
        self.model_changed(rebuild=True)

    def on_command(self, event):
        if self.loading or self.cur_item is None:
            return
        sel = self.ch_cmd.GetString(self.ch_cmd.GetSelection())
        item = self.cur_item
        if sel == '(なし)':
            item.pop('command', None)
        else:
            item['command'] = sel
        item.pop('args', None)
        self.model_changed(rebuild=False, reload_form=True)

    def on_brake_row(self, row):
        self.on_form(None)

    def on_form(self, event):
        """フォームの値を項目 (dict) に書き戻す。kind / command を変えるときは on_kind / on_command が先に直す。"""
        if event is not None:
            event.Skip()
        if self.loading or self.cur_item is None:
            return
        item = self.cur_item
        text = self.txt_label.GetValue()
        if text != '' or 'label' in item:
            item['label'] = text
        self._update_label_hint()
        kind = self.ch_kind.GetString(self.ch_kind.GetSelection())
        if kind == KIND_FOLDER and self.ch_folder.GetSelection() != wx.NOT_FOUND:
            item['folder'] = self.ch_folder.GetString(self.ch_folder.GetSelection())
        side = self.cur[1]
        if side == 'right':
            i = self.ch_exec.GetSelection()
            if i <= 0:
                item.pop('exec', None)
            else:
                item['exec'] = ('tilt', 'trigger')[i - 1]
        for key, ch in (('hold', self.ch_hold), ('block_a', self.ch_blocka), ('latch', self.ch_latch)):
            v = self._get_tri(ch)
            if v is None:
                item.pop(key, None)
            else:
                item[key] = v
        i = self.ch_hud.GetSelection()
        if i <= 0:
            item.pop('hud', None)
        else:
            item['hud'] = HUD_MARKS[i - 1]
        if kind == KIND_ITEM:
            self._write_args(item)
        self.model_changed(rebuild=False)

    def _write_args(self, item):
        cmd = item.get('command')
        args = item.get('args')
        if not isinstance(args, dict):
            args = collections.OrderedDict()
        if cmd == 'vjoy_button':
            raw = self.txt_buttons.GetValue().replace('、', ',').replace(' ', '')
            nums = []
            ok = True
            if raw:
                for p in raw.split(','):
                    if p == '':
                        continue
                    if p.isdigit() and 1 <= int(p) <= 128:
                        nums.append(int(p))
                    else:
                        ok = False
            if not ok:
                self.frame.set_status('ボタン番号は 1〜128 の整数をカンマで区切ってください (今の入力は保存に入れていません)')
            else:
                args.pop('button', None)
                args.pop('buttons', None)
                if len(nums) == 1:
                    args['button'] = nums[0]
                elif len(nums) > 1:
                    args['buttons'] = nums
        elif cmd == 'brake':
            for row in self.brake_rows:
                k = row.spec['key'][len('brake.'):]
                if row.chk.GetValue():
                    args[k] = row.get_value()
                else:
                    args.pop(k, None)
        elif cmd == 'cruise':
            i = self.ch_action.GetSelection()
            if i <= 0:
                args.pop('action', None)
            else:
                args['action'] = CRUISE_ACTIONS[i - 1]
        else:
            return
        if args:
            item['args'] = args
        else:
            item.pop('args', None)

    # ---- 追加・削除・移動 ----
    def _context(self):
        """今の選びから (side, fname) を決める。何も無ければ左のルート。"""
        key = self.cur
        data = self.model.data
        if key is None or key[0] == 'side':
            side = key[1] if key else 'left'
            return side, (panel_root_name(data) if side == 'left' else 'items')
        if key[0] == 'folder':
            return 'left', key[2]
        return key[1], key[2]

    def on_add_slot(self, event):
        side, fname = self._context()
        data = self.model.data
        table = get_table(data, side, fname, create=True)
        root = is_root_level(data, side, fname)
        free = None
        for i in range(1 if root else 2, PANEL_SLOT_MAX + 1):
            if str(i) not in table:
                free = str(i)
                break
        if free is None:
            self.frame.set_status('この階層は {} 個で満杯です'.format(PANEL_SLOT_MAX))
            return
        item = collections.OrderedDict()
        item['label'] = NEW_ITEM_LABEL
        table[free] = item
        self.model_changed(rebuild=True, select=('slot', side, fname, free))

    def on_delete(self, event):
        key = self.cur
        data = self.model.data
        if key is None:
            return
        if key[0] == 'slot':
            table = get_table(data, key[1], key[2])
            if table is not None and key[3] in table:
                del table[key[3]]
                self.model_changed(rebuild=True)
        elif key[0] == 'folder':
            if key[2] == panel_root_name(data):
                self.frame.set_status('ルートのフォルダは消せません')
                return
            if wx.MessageBox("フォルダ '{}' を、中身ごと消しますか?".format(key[2]), '確認', wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
                return
            folders = get_folders(data)
            if folders is not None and key[2] in folders:
                del folders[key[2]]
                self.model_changed(rebuild=True)
        else:
            self.frame.set_status('消せるのはスロットとフォルダです')

    def on_add_folder(self, event):
        dlg = wx.TextEntryDialog(self, 'フォルダの名前 (英数字のほうが安全です)', 'フォルダを足す', 'sub')
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            name = dlg.GetValue().strip()
        finally:
            dlg.Destroy()
        if not name:
            return
        folders = get_folders(self.model.data, create=True)
        if name in folders:
            self.frame.set_status("フォルダ '{}' はもうあります".format(name))
            return
        folders[name] = collections.OrderedDict()
        self.model_changed(rebuild=True, select=('folder', 'left', name))

    def on_move(self, delta):
        key = self.cur
        if key is None or key[0] != 'slot':
            return
        _, side, fname, slot = key
        data = self.model.data
        if not slot.isdigit():
            return
        new = int(slot) + delta
        root = is_root_level(data, side, fname)
        if new < (1 if root else 2) or new > PANEL_SLOT_MAX:
            self.frame.set_status('これ以上は動かせません')
            return
        table = get_table(data, side, fname)
        if table is None or slot not in table:
            return
        new_s = str(new)
        a = table[slot]
        b = table.get(new_s)
        table[new_s] = a
        if b is not None:
            table[slot] = b
        else:
            del table[slot]
        self.model_changed(rebuild=True, select=('slot', side, fname, new_s))

    def on_rename(self, event):
        key = self.cur
        if key is None or key[0] != 'folder':
            return
        old = key[2]
        new = self.txt_fname.GetValue().strip()
        folders = get_folders(self.model.data)
        if not new or new == old or folders is None:
            return
        if new in folders:
            self.frame.set_status("フォルダ '{}' はもうあります".format(new))
            return
        renamed = collections.OrderedDict()
        for n in folders:
            renamed[new if n == old else n] = folders[n]
        sd = get_side(self.model.data, 'left')
        sd['folders'] = renamed
        if str(sd.get('root', 'main')) == old:
            sd['root'] = new
        for n in renamed:
            t = renamed[n]
            if isinstance(t, dict):
                for slot in t:
                    row = t[slot]
                    if isinstance(row, dict) and row.get('folder') == old:
                        row['folder'] = new
        self.model_changed(rebuild=True, select=('folder', 'left', new))

    def on_make_root(self, event):
        key = self.cur
        if key is None or key[0] != 'folder':
            return
        sd = get_side(self.model.data, 'left', create=True)
        sd['root'] = key[2]
        self.model_changed(rebuild=True, select=key)

    # ---- 変更のあとの片づけ ----
    def model_changed(self, rebuild=False, select=None, reload_form=False):
        self.frame.mark_dirty()
        if rebuild:
            self.rebuild_tree(select if select is not None else self.cur)
            return
        if self.cur is not None and self.cur[0] == 'slot' and self.cur_item is not None and self.cur in self.node_of:
            self.tree.SetItemText(self.node_of[self.cur], self._item_text(self.cur[3], self.cur_item))
        if reload_form:
            self.loading = True
            try:
                self.load_slot_form()
            finally:
                self.loading = False
            self.form.Layout()
            self.form.FitInside()
        self.refresh_all_views()

    def refresh_all_views(self):
        self.refresh_preview()
        self.refresh_validation()

    def refresh_preview(self):
        """左右 2 つの見本を作り直す。左 = 今の階層 (右を選んでいる間は最後に見た左の階層。無ければルート)。"""
        key = self.cur
        data = self.model.data
        root = panel_root_name(data)
        if key is not None:
            side, fname = self._context()
            if side == 'left':
                self.left_fname = fname
        folders = get_folders(data)
        if self.left_fname is None or not folders or self.left_fname not in folders:
            self.left_fname = root
        lname = self.left_fname
        hl_l = hl_r = None
        if key is not None and key[0] == 'slot':
            try:
                idx = int(key[3]) - 1
            except Exception:
                idx = None
            if idx is not None and idx >= 0:
                if key[1] == 'left' and key[2] == lname:
                    hl_l = idx
                elif key[1] == 'right':
                    hl_r = idx
        self.preview_l.set_level(level_entries(data, 'left', lname), '左 ' + lname, hl_l)
        self.preview_r.set_level(level_entries(data, 'right', 'items'), '右 items', hl_r)

    def refresh_validation(self):
        problems = validate_panels(self.model.data)
        self.val.DeleteAllItems()
        label = {'error': 'エラー', 'warn': '警告', 'info': '情報'}
        colour = {'error': RED, 'warn': ORANGE, 'info': GRAY}
        if not problems:
            problems = [('info', '', '警告はありません')]
        for i, (lv, where, msg) in enumerate(problems):
            self.val.InsertItem(i, label.get(lv, lv))
            self.val.SetItem(i, 1, where)
            self.val.SetItem(i, 2, msg)
            self.val.SetItemTextColour(i, wx.Colour(*colour.get(lv, GRAY)))


# ==============================================================================
# 窓
# ==============================================================================
class MainFrame(wx.Frame):
    def __init__(self, first_profile=None, log_path=None, status_path=None, cmd_path=None, alive_path=None):
        wx.Frame.__init__(self, None, title='VC コンソール  v{}'.format(VC_GUI_VERSION), size=WINDOW_SIZE)
        self.status_path = status_path or STATUS_PATH
        self.cmd_path = cmd_path or CMD_PATH
        self.alive_path = alive_path or ALIVE_PATH
        self.cockpit_status = None      # 最後に読んだ状態 (止まっていれば None)
        self.model = ProfileModel()
        self.profile_paths = []
        self.CreateStatusBar()
        self.SetMinSize((900, 600))

        root = wx.Panel(self)
        # コクピットの状態の帯 (どのタブでも出す)
        self.head_st = _bold(wx.StaticText(root, label=cockpit_summary(None)))
        # プロファイルの選び (タブ 3 と 4 だけに出す)
        self.bar = wx.Panel(root)
        bh = wx.BoxSizer(wx.HORIZONTAL)
        bh.Add(wx.StaticText(self.bar, label='プロファイル:'), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)
        self.ch_profile = wx.Choice(self.bar, size=(240, -1))
        bh.Add(self.ch_profile, 0, wx.RIGHT, 6)
        self.btn_reload = wx.Button(self.bar, label='再読込 (元に戻す)')
        self.btn_save = wx.Button(self.bar, label='保存')
        self.btn_saveas = wx.Button(self.bar, label='別名で保存')
        for b in (self.btn_reload, self.btn_save, self.btn_saveas):
            bh.Add(b, 0, wx.RIGHT, 6)
        self.dirty_st = _bold(wx.StaticText(self.bar, label=''))
        bh.Add(self.dirty_st, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 8)
        self.bar.SetSizer(bh)

        self.nb = wx.Notebook(root)
        self.cockpit_tab = CockpitTab(self.nb, self)
        self.log_tab = LogTab(self.nb, self, log_path)
        self.config_tab = ConfigTab(self.nb, self)
        self.settings_tab = SettingsTab(self.nb, self)
        self.panel_tab = PanelTab(self.nb, self)
        self.nb.AddPage(self.cockpit_tab, 'コクピット')
        self.nb.AddPage(self.log_tab, 'ログ')
        self.nb.AddPage(self.config_tab, '設定')
        self.nb.AddPage(self.settings_tab, 'プロファイル')
        self.nb.AddPage(self.panel_tab, 'パネル')

        v = wx.BoxSizer(wx.VERTICAL)
        v.Add(self.head_st, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        v.Add(self.bar, 0, wx.ALL, 6)
        v.Add(self.nb, 1, wx.EXPAND)
        root.SetSizer(v)

        self.ch_profile.Bind(wx.EVT_CHOICE, self.on_choose_profile)
        self.btn_reload.Bind(wx.EVT_BUTTON, self.on_reload)
        self.btn_save.Bind(wx.EVT_BUTTON, self.on_save)
        self.btn_saveas.Bind(wx.EVT_BUTTON, self.on_save_as)
        self.nb.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_page)
        self.Bind(wx.EVT_CLOSE, self.on_close)

        self.fill_profile_choice(select_name=first_profile or DEFAULT_PROFILE_FILE)
        self.load_selected(ask=False)
        self.bar.Show(False)
        root.Layout()

        # 1 秒ごとに、生存の印を書き、本体の状態を読む
        self.tick_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_tick, self.tick_timer)
        self.on_tick(None)
        self.tick_timer.Start(TICK_MS)

    # ---- 共通 ----
    def set_status(self, text):
        try:
            self.SetStatusText(text)
        except Exception:
            pass

    def mark_dirty(self):
        self.model.dirty = True
        self.update_dirty_label()

    def update_dirty_label(self):
        self.dirty_st.SetLabel('* 保存していない変更があります' if self.model.dirty else '')
        self.bar.Layout()

    def on_tick(self, event):
        """1 秒ごと: 生存の印を書く → 状態を読んで帯とコクピットのタブに出す。"""
        if not write_alive(self.alive_path):
            self.set_status('生存の印を書けません: {}'.format(self.alive_path))
        try:
            st = read_cockpit_status(self.status_path)
            self.cockpit_status = st
            text = cockpit_summary(st)
            if self.head_st.GetLabel() != text:
                self.head_st.SetLabel(text)
                self.head_st.SetForegroundColour(wx.Colour(*(GREEN if st else GRAY)))
                self.head_st.GetParent().Layout()
            self.cockpit_tab.update_status(st)
        except Exception as e:
            self.set_status('状態を表示できません: {}'.format(e))

    def send_cmd(self, obj):
        """コクピットへ命令を 1 行足す。結果を状態バーに出す。"""
        ok, msg = send_cockpit_cmd(self.cmd_path, obj)
        self.set_status(msg)
        return ok

    def auto_reload_if_current(self, path):
        """保存したファイルがコクピットの今のプロファイルなら、profile_reload を送る。"""
        try:
            st = self.cockpit_status
            if st is None or not same_profile_file(path, st.get('profile_file')):
                return
            if self.send_cmd({'cmd': 'profile_reload'}):
                msg = '保存したのでコクピットに profile_reload を送りました: {}'.format(os.path.basename(path))
                self.set_status(msg)
                self.log_tab.add_note(msg)
        except Exception as e:
            self.set_status('自動の読み直しに失敗: {}'.format(e))

    def on_page(self, event):
        page = self.nb.GetCurrentPage()
        self.bar.Show(page is self.settings_tab or page is self.panel_tab)
        self.bar.GetParent().Layout()
        event.Skip()

    # ---- プロファイルの選び ----
    def fill_profile_choice(self, select_name=None):
        names = list_profile_files()
        self.profile_paths = [os.path.join(PROFILE_DIR, n) for n in names]
        labels = list(names)
        if self.model.path and os.path.abspath(os.path.dirname(self.model.path)) != os.path.abspath(PROFILE_DIR):
            self.profile_paths.append(self.model.path)
            labels.append(self.model.path)
        self.ch_profile.Clear()
        for t in labels:
            self.ch_profile.Append(t)
        want = None
        if self.model.path and self.model.path in self.profile_paths:
            want = self.profile_paths.index(self.model.path)
        elif select_name and select_name in names:
            want = names.index(select_name)
        elif names:
            want = 0
        if want is not None:
            self.ch_profile.SetSelection(want)
        else:
            self.set_status('profiles フォルダに *.json がありません: {}'.format(PROFILE_DIR))

    def confirm_discard(self):
        if not self.model.dirty:
            return True
        return wx.MessageBox('保存していない変更があります。捨てますか?', '確認', wx.YES_NO | wx.ICON_QUESTION) == wx.YES

    def load_selected(self, ask=True):
        i = self.ch_profile.GetSelection()
        if i == wx.NOT_FOUND or i >= len(self.profile_paths):
            self.model.path = None
            self.model.data = collections.OrderedDict()
            self.model.dirty = False
            self.after_model_load()
            return
        ok, msg = self.model.load(self.profile_paths[i])
        self.set_status(msg)
        self.after_model_load()

    def after_model_load(self):
        self.update_dirty_label()
        self.settings_tab.on_model_loaded()
        self.panel_tab.on_model_loaded()

    def on_choose_profile(self, event):
        if not self.confirm_discard():
            if self.model.path in self.profile_paths:
                self.ch_profile.SetSelection(self.profile_paths.index(self.model.path))
            return
        self.load_selected()

    def on_reload(self, event):
        if not self.confirm_discard():
            return
        self.fill_profile_choice()
        self.load_selected()

    def on_save(self, event):
        if not self.model.path:
            self.on_save_as(event)
            return
        ok, msg = self.model.save()
        self.set_status(msg)
        self.update_dirty_label()
        if ok:
            self.auto_reload_if_current(self.model.path)

    def on_save_as(self, event):
        dlg = wx.FileDialog(self, '別名で保存', defaultDir=PROFILE_DIR, defaultFile=os.path.basename(self.model.path or 'new_profile.json'),
                            wildcard='プロファイル (*.json)|*.json', style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
        try:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = dlg.GetPath()
        finally:
            dlg.Destroy()
        ok, msg = self.model.save(path)
        self.set_status(msg)
        if ok:
            self.fill_profile_choice()
            self.auto_reload_if_current(self.model.path)
        self.update_dirty_label()

    def on_close(self, event):
        if self.model.dirty and event.CanVeto():
            if wx.MessageBox('保存していない変更があります。捨てて閉じますか?', '確認', wx.YES_NO | wx.ICON_QUESTION) != wx.YES:
                event.Veto()
                return
        try:
            if event.CanVeto():
                # 窓を閉じる前に、コクピットが動いていれば 3 択で聞く (今の状態を読み直して決める)
                if read_cockpit_status(self.status_path) is not None:
                    choice = ask_close_choice(self)
                    if choice == 'cancel':
                        event.Veto()
                        return
                    if choice == 'quit':
                        self.send_cmd({'cmd': 'quit'})
        except Exception as e:
            self.set_status('閉じる前の確認に失敗: {}'.format(e))
        try:
            self.tick_timer.Stop()
        except Exception:
            pass
        self.log_tab.stop()
        clear_alive(self.alive_path)
        event.Skip()


def parse_args(argv):
    """コマンドラインを読む。返り値 = argparse の Namespace (profile, log, status, cmd, alive)。知らない引数は無視する。"""
    import argparse
    ap = argparse.ArgumentParser(add_help=False)
    ap.add_argument('--profile', default=None)
    ap.add_argument('--log', default=None)
    ap.add_argument('--status', default=STATUS_PATH)
    ap.add_argument('--cmd', default=CMD_PATH)
    ap.add_argument('--alive', default=ALIVE_PATH)
    ap.add_argument('profile_pos', nargs='?', default=None)     # 古い書き方: ファイル名だけ
    try:
        ns, _unknown = ap.parse_known_args(list(argv[1:]))
    except SystemExit:
        ns = ap.parse_args([])      # 引数が壊れていたときは既定で起動する
    if ns.profile is None:
        ns.profile = ns.profile_pos
    return ns


def run(argv=None):
    argv = sys.argv if argv is None else argv
    args = parse_args(argv)
    app = wx.App(False)
    checker = None
    try:
        checker = wx.SingleInstanceChecker('VCConsole-{}'.format(os.environ.get('USERNAME') or os.environ.get('USER') or 'user'))
        if checker.IsAnotherRunning():
            return      # もう動いている。何も言わずに終わる
    except Exception:
        checker = None  # 調べられないときは、そのまま起動する
    frame = MainFrame(first_profile=args.profile, log_path=args.log, status_path=args.status,
                      cmd_path=args.cmd, alive_path=args.alive)
    frame.Show(True)
    app.MainLoop()
    del checker


if __name__ == '__main__':
    # python vc_gui.py で起動したときも steam_vr_wheel を読めるように、親フォルダを探す道に足す
    _parent = os.path.dirname(PACKAGE_DIR)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    run()
